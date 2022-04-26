from __future__ import absolute_import, unicode_literals
from django.conf import settings
from celery import shared_task
import VariantValidator
from . import services
import logging
from django_celery_results.models import TaskResult
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

logger = logging.getLogger('vv')


@shared_task
def validate(variant, genome, transcripts, validator=None):
    logger.info("Running validate task")
    if validator is None:
        validator = VariantValidator.Validator()
    output = validator.validate(variant, genome, transcripts)
    return output.format_as_dict()


@shared_task
def gene2transcripts(symbol, validator=None):
    logger.info("Running gene2transcripts task")
    if validator is None:
        validator = VariantValidator.Validator()
    output = validator.gene2transcripts(symbol)
    return output


@shared_task
def batch_validate(variant, genome, email, gene_symbols, transcripts, options, validator=None):
    logger.info("Running batch_validate task")
    if validator is None:
        validator = VariantValidator.Validator()

    transcript_list = []
    if "all" not in transcripts and "select" not in transcripts:
        transcript_list = transcripts.split('|')
    else:
        pass  # Keep it as 'all or a select'
    for sym in gene_symbols.split('|'):
        if sym:
            returned_trans = gene2transcripts(sym, validator=validator)
            logger.info(returned_trans)
            try:
                for trans in returned_trans['transcripts']:
                    transcript_list.append(trans['reference'])
            except KeyError:
                continue

    if transcript_list is not [] and ('all' not in transcripts and "select" not in transcripts):
        transcripts = "|".join(transcript_list)
    else:
        transcripts = transcripts

    logger.info("Transcripts: %s" % transcripts)
    output = validator.validate(variant, genome, transcripts)
    # Convert to a table
    res = output.format_as_table()
    # Add options to the metadata dictionary
    res[0] = res[0] + ", options: " + str(options)

    logger.info("Now going to send email")
    logger.info(batch_validate.request.id)
    services.send_result_email(email, batch_validate.request.id)
    return res


@shared_task
def vcf2hgvs(vcf_file, genome, gene_symbols, email, transcripts, options, validator=None):
    logger.info("Running vcf2hgvs task")
    if validator is None:
        validator = VariantValidator.Validator()

    qc = False
    batch_list = []
    unprocessed = []
    error_log = []
    total_vcf_calls = 0
    vcf_validated = 0
    batch_submit = True
    jobid = vcf2hgvs.request.id

    for var_call in vcf_file.split('\n'):
        try:
            # REMOVE METADATA
            if var_call.startswith('#'):
                continue
            else:
                # Stringify
                # var_call = var_call.decode()
                var_call = var_call.strip()
                # Log var_call

                # Split the VCF components into a list
                variant_data = var_call.split()
                logger.info(variant_data)

                try:
                    # Gather the call data
                    chr = str(variant_data[0])
                    pos = str(variant_data[1])
                    ref = str(variant_data[3])
                    alt = str(variant_data[4])
                except:
                    continue

                # Create an unambiguous call for VCF 4.0
                if ref == '.' or ref == '' or ref == '-':
                    ref = 'ins'
                if alt == '.' or ref == '' or ref == '-':
                    alt = 'del'

                # Create the pseudo VCF inclusive of reference check
                pvd = services.vcf2psuedo(chr, pos, ref, alt, genome, validator)
                logger.debug(pvd)
                # Analyse the return
                if pvd['valid'] == 'pass':
                    pseudo_vcf = '%s-%s-%s-%s' % (chr, pos, ref, alt)
                    unprocessed.append(pseudo_vcf)
                    error_log.append('Unsupported Variant ' + pseudo_vcf + ' ' + genome)
                    continue
                else:
                    total_vcf_calls += 1
                    pseudo_vcf = pvd['pseudo_vcf']
                    # Add to batch_list
                    batch_list.append(pseudo_vcf)
                    if pvd['valid'] == 'true' or pvd['valid'] == 'ambiguous':
                        vcf_validated += 1

                # Check Genome Build
                # in the first instance at 100 accepted calls
                if total_vcf_calls == 100:
                    qc = True
                    try:
                        ratio_valid = (vcf_validated / total_vcf_calls)
                    except ZeroDivisionError:
                        ratio_valid = 0.0

                    ratio_valid = ratio_valid * 100
                    if ratio_valid < 90:
                        logger.info("Will email as not enough are valid!")
                        error_log.append("Only %s percent valid after processing 100 VCFs" % ratio_valid)
                        services.send_vcf_email(email=email, job_id=jobid, genome=genome, per=ratio_valid)
                        batch_submit = False
                        break

                # Limit jobs in batch list
                elif vcf_validated > settings.MAX_VCF:
                    logger.info("Will email as exceeded max")
                    error_log.append("Exceeded max %s validated VCFs" % settings.MAX_VCF)
                    services.send_vcf_email(email, jobid, cause='max_limit')
                    batch_submit = False
                    break

        except BaseException as error:
            # MANUAL_RESUBMISSION = True

            # Warn admin so that we can resubmit - needs manual intervension
            warning = ("Processing failure in bug catcher 1 - job suspended: {}".format(error))
            logger.warning(warning)
            logger.warning(error)

            # Assemble an error log
            # String the log into a single list
            report_error_log = ['Processsing_error_1'] + [str(warning)]
            # report_error_log = report_error_log + tbk
            error_log = error_log + report_error_log
            continue

    if not qc:
        try:
            ratio_valid = (vcf_validated / total_vcf_calls)
        except ZeroDivisionError:
            ratio_valid = 0.0

        ratio_valid = ratio_valid * 100
        if ratio_valid < 90:
            error_log.append("Only %s percent valid after processing whole file" % ratio_valid)
            logger.info("Will email as not enough valid")
            services.send_vcf_email(email, jobid, genome=genome, per=ratio_valid)
            batch_submit = False

    # Autosubmit to batch?
    if batch_submit:
        logger.info("All good - going to submit to batch validator")
        variants = '|'.join(batch_list)
        logger.debug(variants)
        batch_validate.delay(variants, genome, email, gene_symbols, transcripts, options)
        return 'Success - %s (of %s) variants submitted to BatchValidator' % (len(batch_list), total_vcf_calls)
    logger.error(error_log)
    return {'errors': error_log}


@shared_task()
def delete_old_jobs():
    """
    Task will check for any batch jobs that were completed over 7 days ago and remove them.
    :return:
    """
    logger.info("Checking what job results can be deleted")
    timepoint = timezone.now() - timedelta(days=7)
    print(timepoint)
    jobs = TaskResult.objects.filter(date_done__lte=timepoint)
    print(jobs)
    num, details = jobs.delete()
    logger.info("Deleted %s task results" % num)
    return {'deleted': num, 'detail': details}


@shared_task()
def email_old_users():
    """
    Task will look for users that haven't logged in for 23 months. They will be emailed to inform them that their
    account will be deleted unless they log back in within the next month.
    :return:
    """
    timepoint = timezone.now() - timedelta(days=(365*2 - 30))
    print(timepoint)
    users = User.objects.filter(last_login__lte=timepoint, profile__contacted_for_deletion=False)
    if users:
        logger.info("Sending deletion warning to %s" % users)
    for user in users:
        services.send_user_deletion_warning(user)
        profile = user.profile
        profile.contacted_for_deletion = True
        profile.save()

    # Check for users that have logged in since the email
    active_users = User.objects.filter(last_login__gt=timepoint, profile__contacted_for_deletion=True)
    print(active_users)
    if active_users:
        logger.info("These users have logged back in since email was sent: %s" % active_users)
    for user in active_users:
        profile = user.profile
        profile.contacted_for_deletion = False
        profile.save()

    return "Sent %s emails. %s users are now active" % (len(users), len(active_users))


@shared_task()
def delete_old_users():
    """
    Task will look for users that haven't logged in for 24 months and have received the warning email, then delete their
    accounts.
    :return:
    """
    timepoint = timezone.now() - timedelta(days=(365*2))
    print(timepoint)
    users = User.objects.filter(last_login__lte=timepoint, profile__contacted_for_deletion=True)

    num, details = users.delete()
    logger.info("Deleted %s user accounts due to inactivity" % num)
    return {'deleted': num, 'detail': details}

# <LICENSE>
# Copyright (C) 2016-2022 VariantValidator Contributors
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
