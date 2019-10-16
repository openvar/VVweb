from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.sites.models import Site
from django.conf import settings
from django.utils import timezone
from VariantValidator.modules.seq_data import to_accession


def process_result(val, validator):
    """
    Function will sort through the validation output dictionary, identifying the needed fields to recreate the
    interactive output view.
    :param val: dict
    :param validator: VariantValidator.Validator()
    :return: dict
    """

    flag = val['flag']
    meta = val['metadata']
    input_str = ''
    each = []
    genomes = {}
    counter = 0
    warnings = []
    for k, v in val.items():
        if k == 'flag' or k == 'metadata':
            continue
        print(k)
        counter += 1
        input_str = v['submitted_variant']
        v['id'] = 'res' + str(counter)
        latest = True
        if v['hgvs_transcript_variant']:
            v['safe_hgvs_trans'] = v['hgvs_transcript_variant']
            tx_id_info = validator.hdp.get_tx_identity_info(v['hgvs_transcript_variant'].split(':')[0])
            print(tx_id_info)
            tx_ac = v['hgvs_transcript_variant'].split(':')[0]
            v['tx_ac'] = tx_ac
            acc = tx_ac.split('.')
            version_number = int(acc[1])
            accession = acc[0]
            for trans in list(val.keys()):
                if accession in trans and trans != k:
                    other_version = int(trans.split(':')[0].split('.')[1])
                    if other_version > version_number:
                        latest = False
        else:
            v['tx_ac'] = ''
            v['safe_hgvs_trans'] = 'Unknown transcript variant'

        if v['gene_symbol']:
            gene_info = validator.hdp.get_gene_info(v['gene_symbol'])
            print(gene_info)
            v['chr_loc'] = gene_info[1]

        if v['hgvs_refseqgene_variant']:
            gene_ac = v['hgvs_refseqgene_variant'].split(':')[0]
            v['gene_ac'] = gene_ac
        else:
            v['gene_ac'] = ''

        prot_ac = v['hgvs_predicted_protein_consequence']['tlr'].split(':')[0]
        prot_ac = prot_ac.split('(')[0]
        v['prot_ac'] = prot_ac
        v['latest'] = latest

        for genome in v['primary_assembly_loci']:
            vcfdict = v['primary_assembly_loci'][genome]['vcf']
            vcfstr = "%s:%s:%s:%s:%s" % (
                genome.replace('grch', 'GRCh'),
                vcfdict['chr'],
                vcfdict['pos'],
                vcfdict['ref'],
                vcfdict['alt']
            )
            vcfstr_alt = "%s-%s-%s-%s" % (
                vcfdict['chr'],
                vcfdict['pos'],
                vcfdict['ref'],
                vcfdict['alt']
            )
            v['primary_assembly_loci'][genome]['vcfstr'] = vcfstr
            v['primary_assembly_loci'][genome]['vcfstr_alt'] = vcfstr_alt
            genomes[genome] = vcfstr_alt
            v['primary_assembly_loci'][genome]['ac'] = \
                v['primary_assembly_loci'][genome]['hgvs_genomic_description'].split(':')[0]

        if v['tx_ac'] or v['gene_ac']:
            each.append(v)
        else:
            warnings = v['validation_warnings']

    alloutputs = {
        'flag': flag,
        'meta': meta,
        'inputted': input_str,
        'genomes': genomes,
        'results': sorted(each, key=lambda i: i['tx_ac']),
        'warnings': warnings,
    }

    return alloutputs


def send_initial_email(email, job_id, submitted):
    subject = "VariantValidator Job Submitted"
    current_site = Site.objects.get_current()
    message = render_to_string('email/initial.txt', {
        'job_id': job_id,
        'domain': current_site.domain,
        'sub': submitted,
        'time': timezone.now(),
    })
    html_msg = render_to_string('email/initial.html', {
        'job_id': job_id,
        'domain': current_site.domain,
        'sub': submitted,
        'time': timezone.now(),
    })

    send_mail(subject, message, 'admin@variantValidator.org', [email], html_message=html_msg)


def send_result_email(email, job_id):
    subject = "Batch Validation Report"
    current_site = Site.objects.get_current()
    message = render_to_string('email/report.txt', {'job_id': job_id, 'domain': current_site.domain})
    html_msg = render_to_string('email/report.html', {'job_id': job_id, 'domain': current_site.domain})

    send_mail(subject, message, 'admin@variantValidator.org', [email], html_message=html_msg)


def send_vcf_email(email, job_id, cause='invalid', genome=None, per=0):
    if cause != 'invalid' and cause != 'max_limit':
        raise TypeError("send_vcf_email expects string 'invalid' or 'max_limit'. %s is not accepted" % cause)

    base_template = 'vcf_%s' % cause

    subject = "VCF2HGVS Conversion Rejected"
    current_site = Site.objects.get_current()
    message = render_to_string('email/%s.txt' % base_template,
                               {'domain': current_site.domain,
                                'job_id': job_id,
                                'genome': genome,
                                'per': per,
                                'max': settings.MAX_VCF})
    html_msg = render_to_string('email/%s.html' % base_template,
                                {'domain': current_site.domain,
                                 'job_id': job_id,
                                 'genome': genome,
                                 'per': per,
                                 'max': settings.MAX_VCF})

    send_mail(subject, message, 'admin@variantValidator.org', [email], html_message=html_msg)


def send_contact_email(contact):
    subject = "[Contact Form] New submission from %s" % contact.nameval
    message = render_to_string('email/contact.txt', {'contact': contact})
    html_msg = render_to_string('email/contact.html', {'contact': contact})

    send_mail(subject, message, 'admin@variantValidator.org', settings.ADMIN_EMAILS, html_message=html_msg)


def vcf2psuedo(chromosome, pos, ref, alt, primary_assembly, validator):
    """
    Taken directly from original function in batch validator and tweaked to work with new VV version
    :param chromosome:
    :param pos:
    :param ref:
    :param alt:
    :param primary_assembly:
    :param validator:
    :return:
    """
    chromosome = chromosome.upper()
    # Remove chr from UCSC refs
    if chromosome.startswith('CHR'):
        chromosome = chromosome[3:]

    validation = {'pseudo_vcf': '',
                  'supported': '',
                  'valid': ''
                  }

    # Is there a supported chromosome?
    rs_chr = to_accession(chromosome, primary_assembly)
    print(rs_chr)
    if rs_chr is None:
        validation['supported'] = 'false'
        validation['pseudo_vcf'] = 'false'
        validation['valid'] = 'pass'
    else:
        validation['supported'] = 'true'
        # Now check the reference sequence - fetch the specified bases and check whether they match the stated ref
        if ref == 'ins':
            validation['valid'] = 'ambiguous'
        else:
            start = int(pos)
            end = int(pos) + len(ref) - 1
            mock_hgvs_g = str(rs_chr) + ':g.' + str(start) + '_' + str(end) + 'del'
            get_ref = validator.hgvs2ref(mock_hgvs_g)
            test = get_ref['sequence']
            if ref == test:
                validation['valid'] = 'true'
            else:
                validation['valid'] = 'false'
        # Assemble Pseudo VCF
        validation['pseudo_vcf'] = '%s-%s-%s-%s' % (chromosome, pos, ref, alt)

    # Return the result
    return validation
