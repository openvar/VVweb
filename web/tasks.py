from __future__ import absolute_import, unicode_literals
from celery import shared_task
import VariantValidator
from . import services


@shared_task
def validate(variant, genome, transcripts='all', validator=None):
    if validator is None:
        validator = VariantValidator.Validator()
    output = validator.validate(variant, genome, transcripts)
    return output.format_as_dict()


@shared_task
def gene2transcripts(symbol, validator=None):
    if validator is None:
        validator = VariantValidator.Validator()
    output = validator.gene2transcripts(symbol)
    return output


@shared_task
def batch_validate(variant, genome, email, gene_symbols, validator=None):
    if validator is None:
        validator = VariantValidator.Validator()

    transcripts = []
    for sym in gene_symbols.split('|'):
        if sym:
            returned_trans = gene2transcripts(sym, validator=validator)
            print(returned_trans)
            for trans in returned_trans['transcripts']:
                transcripts.append(trans['reference'])
    if transcripts:
        transcripts = '|'.join(transcripts)
    else:
        transcripts = 'all'

    print("Transcripts: %s" % transcripts)
    output = validator.validate(variant, genome, transcripts)
    res = output.format_as_table()

    print("Now going to send email")
    print(batch_validate.request.id)
    services.send_result_email(email, batch_validate.request.id)
    return res
