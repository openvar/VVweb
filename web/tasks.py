from __future__ import absolute_import, unicode_literals
from django.conf import settings
from celery import shared_task
from . import input_formatting
from . import services
from .object_pool import vval_object_pool, g2t_object_pool, batch_object_pool
import logging
from django_celery_results.models import TaskResult
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
import time
import traceback

logger = logging.getLogger('vv')


# -------------------------------------------------------------------------
# Utility: safely record user_id inside TaskResult.meta
# -------------------------------------------------------------------------

def _store_user_meta(task_id, user_id):
    if not user_id:
        return
    try:
        tr = TaskResult.objects.get(task_id=task_id)
        meta = tr.meta or {}
        meta["user_id"] = user_id
        tr.meta = meta
        tr.save(update_fields=["meta"])
    except TaskResult.DoesNotExist:
        pass


# -------------------------------------------------------------------------
# User-facing tasks
# -------------------------------------------------------------------------

@shared_task(bind=True)
def validate(self, variant, genome, transcripts, validator=None, transcript_set="refseq", user_id=None):
    _store_user_meta(self.request.id, user_id)

    logger.info("Running validate task")
    if validator is None:
        validator = vval_object_pool.get_object()
    try:
        output = validator.validate(
            variant,
            genome,
            transcripts,
            transcript_set=transcript_set,
            lovd_syntax_check=True
        )
    except Exception as e:
        logger.error(f"{variant} {genome} {transcripts} failed with exception {e}")
        raise

    return output.format_as_dict()


@shared_task(bind=True)
def gene2transcripts(self, symbol, validator=None, select_transcripts="all",
                     transcript_set="refseq", lovd_syntax_check=True, user_id=None):
    _store_user_meta(self.request.id, user_id)

    logger.info("Running gene2transcripts task")
    if validator is None:
        validator = g2t_object_pool.get_object()

    output = validator.gene2transcripts(
        symbol,
        select_transcripts=select_transcripts,
        transcript_set=transcript_set,
        bypass_genomic_spans=True,
        lovd_syntax_check=lovd_syntax_check
    )
    return output


@shared_task(bind=True)
def batch_validate(self, variant, genome, email, gene_symbols, transcripts, options=[],
                   transcript_set="refseq", validator=None, user_id=None):

    _store_user_meta(self.request.id, user_id)
    logger.error("Running batch_validate task")

    # Wait for the validator object to become free
    while validator is None:
        validator = batch_object_pool.get_object()
        if validator is None:
            logger.info("Validator not available, waiting for 1 minute...")
            time.sleep(60)

    # ---------------------------------------------------------------------
    # Original logic preserved
    # ---------------------------------------------------------------------
    variant = input_formatting.format_input(variant)
    transcripts = input_formatting.format_input(transcripts)

    if "all" in transcripts:
        transcripts = "all"
    if transcripts == '["raw"]':
        transcripts = "raw"
    if transcripts == '["mane"]':
        transcripts = "mane"
    if transcripts == '["mane_select"]' or "mane_select" in transcripts:
        transcripts = "mane_select"
    if transcripts == '["select"]':
        transcripts = "select"

    transcript_list = []
    for sym in gene_symbols.split('|'):
        if sym:
            returned_trans = gene2transcripts(
                sym,
                validator=validator,
                transcript_set=transcript_set
            )
            logger.info(returned_trans)

            try:
                for trans in returned_trans['transcripts']:
                    transcript_list.append(trans['reference'])
            except KeyError:
                continue

    if len(transcript_list) >= 1:
        transcripts = "|".join(transcript_list)
        transcripts = input_formatting.format_input(transcripts)

    try:
        output = validator.validate(
            variant, genome, transcripts,
            transcript_set=transcript_set,
            lovd_syntax_check=True
        )
    except Exception as e:
        logger.error(f"{variant} {genome} {transcripts} failed with exception {e}")
        trace = traceback.format_exc()
        batch_object_pool.return_object(validator)
        services.send_fail_email(
            email,
            batch_validate.request.id,
            variant, genome, transcripts, transcript_set, trace
        )
        raise

    # Return validator to pool
    batch_object_pool.return_object(validator)

    # Convert to a table
    res = output.format_as_table()
    res[0] = res[0] + ", options: " + str(options)

    logger.info("Now going to send email")
    logger.info(batch_validate.request.id)
    services.send_result_email(email, batch_validate.request.id)
    return res


@shared_task(bind=True)
def vcf2hgvs(self, vcf_file, genome, gene_symbols, email, transcripts, options, validator=None, user_id=None):

    _store_user_meta(self.request.id, user_id)
    logger.info("Running vcf2hgvs task")

    # Wait for validator
    while validator is None:
        validator = batch_object_pool.get_object()
        if validator is None:
            logger.info("Validator not available, waiting for 1 minute...")
            time.sleep(60)

    qc = False
    batch_list = []
    unprocessed = []
    error_log = []
    total_vcf_calls = 0
    vcf_validated = 0
    batch_submit = True
    jobid = self.request.id

    # ---------------------------------------------------------------------
    # Main VCF processing loop (unchanged)
    # ---------------------------------------------------------------------
    for var_call in vcf_file.split('\n'):
        try:
            if var_call.startswith('#'):
                continue
            else:
                var_call = var_call.strip()
                variant_data = var_call.split()
                logger.info(variant_data)

                try:
                    chr = str(variant_data[0])
                    pos = str(variant_data[1])
                    ref = str(variant_data[3])
                    alt = str(variant_data[4])
                except:
                    continue

            if ref in ('.', '', '-'):
                ref = 'ins'
            if alt in ('.', '', '-'):
                alt = 'del'

            pvd = services.vcf2psuedo(chr, pos, ref, alt, genome, validator)

            if pvd['valid'] == 'pass':
                pseudo_vcf = '%s-%s-%s-%s' % (chr, pos, ref, alt)
                unprocessed.append(pseudo_vcf)
                error_log.append('Unsupported Variant ' + pseudo_vcf + ' ' + genome)
                continue
            else:
                total_vcf_calls += 1
                pseudo_vcf = pvd['pseudo_vcf']
                batch_list.append(pseudo_vcf)
                if pvd['valid'] in ('true', 'ambiguous'):
                    vcf_validated += 1

            if total_vcf_calls == 100:
                qc = True
                try:
                    ratio_valid = (vcf_validated / total_vcf_calls) * 100
                except ZeroDivisionError:
                    ratio_valid = 0.0

                if ratio_valid < 90:
                    error_log.append(f"Only {ratio_valid} percent valid after 100 VCFs")
                    services.send_vcf_email(
                        email=email, job_id=jobid, genome=genome, per=ratio_valid
                    )
                    batch_submit = False
                    break

            elif vcf_validated > settings.MAX_VCF:
                error_log.append(f"Exceeded max {settings.MAX_VCF} validated VCFs")
                services.send_vcf_email(email, jobid, cause='max_limit')
                batch_submit = False
                break

        except BaseException as error:
            warning = ("Processing failure in bug catcher 1 - job suspended: {}".format(error))
            logger.warning(warning)
            logger.error(error)
            report_error_log = ['Processsing_error_1'] + [str(warning)]
            error_log = error_log + report_error_log
            continue

    if not qc:
        try:
            ratio_valid = (vcf_validated / total_vcf_calls) * 100
        except ZeroDivisionError:
            ratio_valid = 0.0

        if ratio_valid < 90:
            error_log.append(f"Only {ratio_valid} percent valid after full file")
            services.send_vcf_email(email, jobid, genome=genome, per=ratio_valid)
            batch_submit = False

    if batch_submit:
        logger.info("All good - going to submit to batch validator")
        variants = '|'.join(batch_list)
        logger.debug(variants)

        # IMPORTANT: propagate user_id to batch_validate
        batch_validate.delay(
            variants, genome, email, gene_symbols, transcripts, options,
            user_id=user_id
        )

        return f"Success - {len(batch_list)} (of {total_vcf_calls}) variants submitted"

    logger.error(error_log)
    return {'errors': error_log}


# -------------------------------------------------------------------------
# System tasks (no user_id)
# -------------------------------------------------------------------------

@shared_task()
def delete_old_jobs():
    """
    Delete task results older than 7 days.
    """
    logger.info("Checking what job results can be deleted")
    timepoint = timezone.now() - timedelta(days=7)
    jobs = TaskResult.objects.filter(date_done__lte=timepoint)
    num, details = jobs.delete()
    logger.info("Deleted %s task results" % num)
    return {'deleted': num, 'detail': details}


@shared_task()
def email_old_users():
    """
    Email users inactive for 23 months.
    """
    timepoint = timezone.now() - timedelta(days=(365 * 2 - 30))
    users = User.objects.filter(last_login__lte=timepoint, profile__contacted_for_deletion=False)

    if users:
        logger.info("Sending deletion warning to %s" % users)

    for user in users:
        services.send_user_deletion_warning(user)
        profile = user.profile
        profile.contacted_for_deletion = True
        profile.save()

    active_users = User.objects.filter(last_login__gt=timepoint, profile__contacted_for_deletion=True)
    if active_users:
        logger.info("Users logged in after email: %s" % active_users)

    for user in active_users:
        profile = user.profile
        profile.contacted_for_deletion = False
        profile.save()

    return "Sent %s emails. %s users active" % (len(users), len(active_users))


@shared_task()
def delete_old_users():
    """
    Delete users inactive for 24 months and previously warned.
    """
    timepoint = timezone.now() - timedelta(days=(365 * 2))
    users = User.objects.filter(last_login__lte=timepoint, profile__contacted_for_deletion=True)
    num, details = users.delete()
    logger.info("Deleted %s user accounts due to inactivity" % num)
    return {'deleted': num, 'detail': details}

# <LICENSE>
# Copyright (C) 2016-2026 VariantValidator Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# </LICENSE>
