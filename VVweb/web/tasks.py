# web/tasks.py
from __future__ import absolute_import, unicode_literals

import json
import logging
import time
import traceback
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django_celery_results.models import TaskResult
from django.contrib.auth import get_user_model

from . import input_formatting
from . import services
from .object_pool import vval_object_pool, g2t_object_pool, batch_object_pool
from .models import VariantQuota
from django.db import connection

try:
    from allauth.socialaccount.models import SocialAccount
except Exception:
    SocialAccount = None

logger = logging.getLogger(__name__)

# Load Django user model once (correct way)
User = get_user_model()


# -------------------------------------------------------------------------
# Utility: ensure a real authenticated user exists
# -------------------------------------------------------------------------
def _ensure_user(user_id):
    """Ensure tasks are only run by authenticated users."""
    if user_id is None:
        raise ValueError("Authenticated user_id required for this task.")
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise ValueError("User with id=%s does not exist." % user_id)


# -------------------------------------------------------------------------
# Utility: store user_id into TaskResult.meta (for admin)
# -------------------------------------------------------------------------
def _store_user_meta(task_id, user_id):
    """Store user information in TaskResult.meta for easier debugging."""
    if not user_id:
        return

    try:
        tr = TaskResult.objects.get(task_id=task_id)
        meta = tr.meta or {}

        # Always store the user_id
        meta["user_id"] = user_id

        # Store the email too, if possible
        try:
            user = User.objects.get(id=user_id)
            meta["email"] = user.email
        except User.DoesNotExist:
            meta["email"] = None

        # Save updated metadata
        tr.meta = meta
        tr.save(update_fields=["meta"])

    except TaskResult.DoesNotExist:
        # No TaskResult created yet — Celery may write it later.
        pass




# -------------------------------------------------------------------------
# USER-FACING TASKS
# -------------------------------------------------------------------------

@shared_task(bind=True)
def validate(
    self,
    variant,
    genome,
    transcripts,
    validator=None,
    transcript_set="refseq",
    user_id=None,
):
    """Single-variant validation (sync inside Celery worker)."""

    _ensure_user(user_id)
    _store_user_meta(self.request.id, user_id)

    logger.info("validate(): user_id=%s variant=%s genome=%s" %
                (user_id, variant, genome))

    # Acquire validator if not provided
    created_validator = False
    if validator is None:
        validator = vval_object_pool.get_object()
        created_validator = True

    try:
        output = validator.validate(
            variant,
            genome,
            transcripts,
            transcript_set=transcript_set,
            lovd_syntax_check=True,
        )
        return output.format_as_dict()

    except Exception as e:
        logger.error("validate(): error for variant=%s user_id=%s : %s" %
                     (variant, user_id, e))
        raise

    finally:
        # Always return validator if acquired here
        if created_validator:
            vval_object_pool.return_object(validator)


@shared_task(bind=True)
def gene2transcripts(
    self,
    symbol,
    validator=None,
    select_transcripts="all",
    transcript_set="refseq",
    lovd_syntax_check=True,
    user_id=None,
):
    """Gene → transcripts lookup (sync inside Celery worker)."""

    _ensure_user(user_id)
    _store_user_meta(self.request.id, user_id)

    logger.info("gene2transcripts(): user_id=%s symbol=%s" %
                (user_id, symbol))

    # Acquire validator only if not supplied
    created_validator = False
    if validator is None:
        validator = g2t_object_pool.get_object()
        created_validator = True

    try:
        return validator.gene2transcripts(
            symbol,
            select_transcripts=select_transcripts,
            transcript_set=transcript_set,
            bypass_genomic_spans=True,
            lovd_syntax_check=lovd_syntax_check,
        )

    except Exception as e:
        logger.error("gene2transcripts(): error for symbol=%s user_id=%s : %s" %
                     (symbol, user_id, e))
        raise

    finally:
        # Only return validator if we acquired it
        if created_validator:
            g2t_object_pool.return_object(validator)


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
    validator=None,
    reserved_n=None,
):
    """Full batch validator (secure, synchronous inside worker)."""

    _ensure_user(user_id)
    _store_user_meta(self.request.id, user_id)

    logger.info("batch_validate(): user_id=%s genome=%s" %
                (user_id, genome))

    if options is None:
        options = []

    # ------------------------------------------------------------------
    # Acquire batch validator from pool
    # ------------------------------------------------------------------
    if validator is None:
        validator = batch_object_pool.get_object()
        wait_cycles = 0

        while validator is None:
            wait_cycles += 1
            logger.info("batch_validate(): pool empty, waiting...")
            time.sleep(5)   # shorter wait, less worker blocking
            validator = batch_object_pool.get_object()
            if wait_cycles > 120:  # 10 minutes max
                raise RuntimeError("No batch validator available after 10 minutes.")

    # ------------------------------------------------------------------
    # Input formatting
    # ------------------------------------------------------------------
    variant = input_formatting.format_input(variant)
    transcripts = input_formatting.format_input(transcripts)

    # Normalise transcript selector
    trans_raw = transcripts
    if "all" in trans_raw:
        transcripts = "all"
    elif trans_raw in ('["raw"]', '["mane"]', '["select"]'):
        transcripts = trans_raw.strip('["]')
    elif "mane_select" in trans_raw:
        transcripts = "mane_select"

    # ------------------------------------------------------------------
    # Expand gene symbols → transcripts
    # ------------------------------------------------------------------
    transcript_list = []

    for sym in gene_symbols.split('|'):
        sym = sym.strip()
        if not sym:
            continue

        try:
            returned = validator.gene2transcripts(
                sym,
                select_transcripts="all",
                transcript_set=transcript_set,
                bypass_genomic_spans=True,
            )

            for tr in returned.get('transcripts', []):
                transcript_list.append(tr['reference'])

        except Exception as e:
            logger.error("batch_validate(): failed gene lookup for %s (%s)" %
                         (sym, e))
            continue

    # If any transcript discovered → override transcripts
    if transcript_list:
        transcripts = input_formatting.format_input("|".join(transcript_list))

    # ------------------------------------------------------------------
    # Perform validation
    # ------------------------------------------------------------------
    try:
        output = validator.validate(
            variant,
            genome,
            transcripts,
            transcript_set=transcript_set,
            lovd_syntax_check=True,
        )

    except Exception as e:
        trace = traceback.format_exc()

        # Return validator before sending email
        batch_object_pool.return_object(validator)

        services.send_fail_email(
            email,
            self.request.id,
            variant,
            genome,
            transcripts,
            transcript_set,
            trace
        )

        logger.error("batch_validate(): validation failure user_id=%s (%s)" %
                     (user_id, e))

        # -------------------------------------------------
        # QUOTA ROLLBACK (ONLY ON CRASH)
        # -------------------------------------------------
        if reserved_n and user_id:
            try:
                quota = VariantQuota.objects.get(user_id=user_id)
                quota.count = max(quota.count - reserved_n, 0)
                quota.save(update_fields=["count"])
            except Exception as qe:
                logger.critical(
                    "FAILED quota rollback for user %s after batch crash (%s)" %
                    (user_id, qe)
                )

        raise

    # SAFE return to pool
    batch_object_pool.return_object(validator)

    # ------------------------------------------------------------------
    # Format output into table
    # ------------------------------------------------------------------
    res = output.format_as_table()
    res[0] += ", options: " + str(options)

    services.send_result_email(email, self.request.id)

    # ------------------------------------------------------------------
    # Populate TaskResult metadata
    # ------------------------------------------------------------------
    try:
        tr = TaskResult.objects.get(task_id=self.request.id)
        tr.task_name = self.name
        tr.task_args = "[]"
        tr.task_kwargs = json.dumps({
            "variant": variant,
            "genome": genome,
            "email": email,
            "gene_symbols": gene_symbols,
            "transcripts": transcripts,
            "options": options,
            "transcript_set": transcript_set,
            "user_id": user_id,
        })
        tr.worker = self.request.hostname
        tr.save(update_fields=["task_name", "task_args", "task_kwargs", "worker"])

    except Exception as e:
        logger.error("batch_validate(): failed to update TaskResult (%s)" % e)

    # ------------------------------------------------------------------
    # Final return
    # ------------------------------------------------------------------
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

# -------------------------------------------------------------------------
# MAINTENANCE TASKS
# -------------------------------------------------------------------------

@shared_task(name="system.delete_old_jobs")
def delete_old_jobs():
    """Delete Celery task results older than 7 days."""
    logger.info("delete_old_jobs(): checking for expired task results")

    timepoint = timezone.now() - timedelta(days=7)
    jobs = TaskResult.objects.filter(date_done__lte=timepoint)

    num, details = jobs.delete()

    logger.info("delete_old_jobs(): deleted %s old task results" % num)
    return {"deleted": num, "detail": details}


@shared_task(name="system.email_old_users")
def email_old_users():
    """
    Email users inactive for ~2 years minus 30 days, warning them their accounts
    will be deleted unless they log in again.
    """
    timepoint = timezone.now() - timedelta(days=(365 * 2 - 30))

    users = User.objects.filter(
        last_login__lte=timepoint,
        profile__contacted_for_deletion=False
    )

    count = users.count()
    if count:
        logger.info("email_old_users(): sending deletion warnings to %s users" % count)

    # Send warnings + mark as contacted
    for user in users:
        services.send_user_deletion_warning(user)
        user.profile.contacted_for_deletion = True
        user.profile.save()

    # Users who became active again after warnings
    active = User.objects.filter(
        last_login__gt=timepoint,
        profile__contacted_for_deletion=True
    )

    for user in active:
        user.profile.contacted_for_deletion = False
        user.profile.save()

    return {
        "warned": count,
        "reactivated": active.count()
    }


@shared_task(name="system.delete_old_users")
def delete_old_users():
    """Delete users inactive for more than 2 years AND previously warned."""
    logger.info("delete_old_users(): checking for inactive user accounts")

    timepoint = timezone.now() - timedelta(days=365 * 2)

    users = User.objects.filter(
        last_login__lte=timepoint,
        profile__contacted_for_deletion=True
    )

    user_ids = list(users.values_list("id", flat=True))
    if not user_ids:
        logger.info("delete_old_users(): no inactive users found")
        return {"deleted": 0}

    # --------------------------------------------------
    # Social account cleanup (ALWAYS attempt)
    # --------------------------------------------------
    social_count = 0

    if SocialAccount is not None:
        # ✅ ORM path
        social_qs = SocialAccount.objects.filter(user_id__in=user_ids)
        social_count = social_qs.count()

        if social_count:
            logger.info(
                "delete_old_users(): deleting %s associated social accounts (ORM)",
                social_count
            )
            social_qs.delete()

    else:
        # Raw SQL fallback (legacy cleanup)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM socialaccount_socialaccount
                WHERE user_id = ANY(%s)
                """,
                [user_ids],
            )
            social_count = cursor.rowcount

        if social_count:
            logger.info(
                "delete_old_users(): deleted %s associated social accounts (SQL)",
                social_count
            )

    # --------------------------------------------------
    # Delete users
    # --------------------------------------------------
    num, details = users.delete()

    logger.info(
        "delete_old_users(): deleted %s user records (social accounts removed: %s)",
        num,
        social_count
    )

    return {
        "users_deleted": num,
        "social_accounts_deleted": social_count,
        "detail": details,
    }

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
