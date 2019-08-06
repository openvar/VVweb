from __future__ import absolute_import, unicode_literals
from celery import shared_task
import VariantValidator


@shared_task
def validate(variant, genome, transcripts='all', validator=None):
    if validator is None:
        validator = VariantValidator.Validator()
    output = validator.validate(variant, genome, transcripts)
    return output.format_as_dict()


@shared_task
def gene2transcripts(variant, validator=None):
    if validator is None:
        validator = VariantValidator.Validator()
    output = validator.gene2transcripts(variant)
    return output


@shared_task
def batch_validate(variant, genome, transcripts='all', validator=None):
    if validator is None:
        validator = VariantValidator.Validator()
    output = validator.validate(variant, genome, transcripts)
    print("Now going to send email")
    return output.format_as_dict()
