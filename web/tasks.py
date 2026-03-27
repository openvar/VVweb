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
# Store user_id safely into TaskResult.meta
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

    return validator.gene2transcripts(
        symbol,
        select_transcripts=select_transcripts,
        transcript_set=transcript_set,
        bypass_genomic_spans=True,
        lovd_syntax_check=lovd_syntax_check
    )



@shared_task(bind=True)
def batch_validate(
    self,
    variant,
    genome,
    email,
    gene_symbols,
    transcripts,
    options=None,
    transcript_set="refseq",
    user_id=None,
    validator=None):

    _store_user_meta(self.request.id, user_id)

    logger.error("Running batch_validate task")

    if options is None:
        options = []

    # ---------------------------------------------------------------------
    # Wait for validator object
    # ---------------------------------------------------------------------
    while validator is None:
        validator = batch_object_pool.get_object()
        if validator is None:
            logger.info("Validator not available, waiting for 1 minute...")
            time.sleep(60)

    # ---------------------------------------------------------------------
    # Process input
    # ---------------------------------------------------------------------
    variant = input_formatting.format_input(variant)
    transcripts = input_formatting.format_input(transcripts)

    trans_raw = transcripts
    if "all" in trans_raw:
        transcripts = "all"
    elif trans_raw == '["raw"]':
        transcripts = "raw"
    elif trans_raw == '["mane"]':
        transcripts = "mane"
    elif trans_raw == '["mane_select"]' or "mane_select" in trans_raw:
        transcripts = "mane_select"
    elif trans_raw == '["select"]':
        transcripts = "select"

    # ---------------------------------------------------------------------
    # Expand gene symbols → transcripts
    # ---------------------------------------------------------------------
    transcript_list = []
    for sym in gene_symbols.split('|'):
        if not sym:
            continue

        # PASS user_id DOWNSTREAM
        returned_trans = gene2transcripts(
            sym,
            validator=validator,
            transcript_set=transcript_set,
            user_id=user_id
        )

        logger.info(returned_trans)

        try:
            for trans in returned_trans['transcripts']:
                transcript_list.append(trans['reference'])
        except KeyError:
            continue

    if transcript_list:
        transcripts = "|".join(transcript_list)
        transcripts = input_formatting.format_input(transcripts)

    # ---------------------------------------------------------------------
    # Now validate
    # ---------------------------------------------------------------------
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
            self.request.id,
            variant, genome, transcripts, transcript_set, trace
        )
        raise

    # return validator to pool
    batch_object_pool.return_object(validator)

    # Create output table
    res = output.format_as_table()
    res[0] = res[0] + ", options: " + str(options)

    logger.info("Sending result email for job %s" % self.request.id)
    services.send_result_email(email, self.request.id)

    return {
        "result": res,
        "user_id": user_id,
        "variant": variant,
        "genome": genome,
        "email": email,
        "gene_symbols": gene_symbols,
        "transcripts": transcripts,
        "options": options,
        "transcript_set": transcript_set,
        "task_id": self.request.id,
        "task_name": self.name,
    }


@shared_task(bind=True)
def vcf2hgvs(self, vcf_file, genome, gene_symbols, email, transcripts, options, validator=None, user_id=None):

    _store_user_meta(self.request.id, user_id)
    logger.info("Running vcf2hgvs task")

    # (unchanged logic)

    # IMPORTANT: propagate user_id to batch_validate
    batch_validate.delay(
        variants, genome, email, gene_symbols, transcripts, options,
        user_id=user_id
    )

    return f"Success - {len(batch_list)} (of {total_vcf_calls}) variants submitted"


# -------------------------------------------------------------------------
# Non-user tasks (no user_id)
# -------------------------------------------------------------------------

@shared_task()
def delete_old_jobs():
    logger.info("Checking what job results can be deleted")
    timepoint = timezone.now() - timedelta(days=7)
    jobs = TaskResult.objects.filter(date_done__lte=timepoint)
    num, details = jobs.delete()
    logger.info("Deleted %s task results" % num)
    return {'deleted': num, 'detail': details}


@shared_task()
def email_old_users():
    timepoint = timezone.now() - timedelta(days=(365 * 2 - 30))
    users = User.objects.filter(last_login__lte=timepoint, profile__contacted_for_deletion=False)

    if users:
        logger.info("Sending deletion warning to %s" % users)

    for user in users:
        services.send_user_deletion_warning(user)
        user.profile.contacted_for_deletion = True
        user.profile.save()

    active = User.objects.filter(last_login__gt=timepoint, profile__contacted_for_deletion=True)
    for user in active:
        user.profile.contacted_for_deletion = False
        user.profile.save()

    return "Sent %s emails. %s users active" % (len(users), len(active))


@shared_task()
def delete_old_users():
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
