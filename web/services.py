from django.core.mail import send_mail, mail_admins
from django.template.loader import render_to_string
from django.contrib.sites.models import Site
from django.conf import settings
from django.utils import timezone
from django.shortcuts import reverse
from VariantValidator.modules.seq_data import to_accession, to_chr_num_ucsc
from VariantValidator.modules.utils import valstr
from vvhgvs import normalizer
import logging
import json

logger = logging.getLogger('vv')


def process_result(val, validator):
    """
    Function will sort through the validation output dictionary, identifying the needed fields to recreate the
    interactive output view.
    :param val: dict
    :param validator: VariantValidator.Validator()
    :return: dict
    """
    logger.debug("Processing validator results")
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
        counter += 1
        input_str = v['submitted_variant']
        v['id'] = 'res' + str(counter)
        latest = True
        if v['hgvs_transcript_variant']:
            v['safe_hgvs_trans'] = v['hgvs_transcript_variant']
            # tx_id_info = validator.hdp.get_tx_identity_info(v['hgvs_transcript_variant'].split(':')[0])
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
            if flag == 'mitochondrial':
                v['safe_hgvs_trans'] = 'Mitochondrial Variant'
            elif "validation_warning" in k:
                v['tx_ac'] = k
                latest = False
                v['safe_hgvs_trans'] = 'Validation Warning'
            else:
                v['safe_hgvs_trans'] = 'Intergenic Variant'

        if v['gene_symbol']:
            try:
                gene_info = validator.hdp.get_gene_info(v['gene_symbol'])
                v['chr_loc'] = gene_info[1]
            except TypeError:
                pass

        if v['hgvs_refseqgene_variant']:
            gene_ac = v['hgvs_refseqgene_variant'].split(':')[0]
            v['gene_ac'] = gene_ac
        else:
            v['gene_ac'] = ''

        # Collect LRG data
        if v['hgvs_lrg_variant']:
            lrg_ac = v['hgvs_lrg_variant'].split(':')[0]
            v['lrg_ac'] = lrg_ac
        else:
            v['lrg_ac'] = ''

        if v['hgvs_lrg_transcript_variant']:
            lrg_tac = v['hgvs_lrg_transcript_variant'].split(':')[0]
            v['lrg_tx_ac'] = lrg_tac
        else:
            v['lrg_tx_ac'] = ''

        if v['hgvs_predicted_protein_consequence']['tlr'] is not None:
            prot_ac = v['hgvs_predicted_protein_consequence']['tlr'].split(':')[0]
            prot_ac = prot_ac.split('(')[0]
            v['prot_ac'] = prot_ac
        else:
            v['prot_ac'] = None

        v['latest'] = latest

        try:
            for genome in v['primary_assembly_loci']:
                try:
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

                except Exception:
                    pass
                v['primary_assembly_loci'][genome]['ac'] = \
                    v['primary_assembly_loci'][genome]['hgvs_genomic_description'].split(':')[0]
                if 'grc' in genome:
                    v['primary_assembly_loci'][genome]['genome'] = genome.replace('grch', 'GRCh')
                else:
                    v['primary_assembly_loci'][genome]['genome'] = genome
        except Exception:
            pass

        for alt in v['alt_genomic_loci']:
            for genome in alt:
                try:
                    vcfdict = alt[genome]['vcf']
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
                    alt[genome]['vcfstr'] = vcfstr
                    alt[genome]['vcfstr_alt'] = vcfstr_alt
                    genomes[genome] = vcfstr_alt
                except Exception:
                    pass
            
                alt[genome]['ac'] = \
                    alt[genome]['hgvs_genomic_description'].split(':')[0]
                if 'grc' in genome:
                    alt[genome]['genome'] = genome.replace('grch', 'GRCh')
                else:
                    alt[genome]['genome'] = genome

        if v['tx_ac'] or v['gene_ac'] or "intergenic_variant" or "mitochondrial" or "validation_warning" in k:
            each.append(v)
            if "intergenic_variant" or "mitochondrial" or "validation_warning" in k:
                warnings = v['validation_warnings']
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
    logger.debug("Sending job submission email")
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
    logger.debug("Sending batch validation results email")
    subject = "Batch Validation Report"
    current_site = Site.objects.get_current()
    message = render_to_string('email/report.txt', {'job_id': job_id, 'domain': current_site.domain})
    html_msg = render_to_string('email/report.html', {'job_id': job_id, 'domain': current_site.domain})

    send_mail(subject, message, 'admin@variantValidator.org', [email], html_message=html_msg)


def send_fail_email(email, job_id, variant, genome, transcripts, transcript_set, trace):
    logger.debug("Sending batch validation fail email")

    # Define the subject for the email
    subject = "Batch Validation Failed"

    # Get the current site (to dynamically include domain in the email)
    current_site = Site.objects.get_current()

    # Convert JSON arrays to string for email formatting (if needed)
    variant_str = json.dumps(variant, indent=2) if isinstance(variant, list) else str(variant)
    transcripts_str = json.dumps(transcripts, indent=2) if isinstance(transcripts, list) else str(transcripts)

    # Update the message and html_msg by passing additional context variables
    message = render_to_string('email/fail_report.txt', {
        'job_id': job_id,
        'domain': current_site.domain,
        'variant': variant_str,
        'genome': genome,
        'transcripts': transcripts_str,
        'transcript_set': transcript_set,
        'trace': trace,
    })

    html_msg = render_to_string('email/fail_report.html', {
        'job_id': job_id,
        'domain': current_site.domain,
        'variant': variant_str,
        'genome': genome,
        'transcripts': transcripts_str,
        'transcript_set': transcript_set,
        'trace': trace,
    })

    # Send the email with the updated content
    send_mail(subject, message, 'admin@variantValidator.org',
              [email, 'admin@variantValidator.org'], html_message=html_msg)


def send_vcf_email(email, job_id, cause='invalid', genome=None, per=0):
    logger.debug("Sending VCF2HGVS error email")
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
    logger.debug("Sending contact form submission to admins")
    subject = "[Contact Form] New submission from %s" % contact.nameval
    message = render_to_string('email/contact.txt', {'contact': contact})
    html_msg = render_to_string('email/contact.html', {'contact': contact})

    mail_admins(subject, message, html_message=html_msg)


def send_user_deletion_warning(user):
    logger.debug("Sending email warning of account deletion to %s" % user)
    subject = "Warning VariantValidator account will soon be deleted"
    current_site = Site.objects.get_current()
    message = render_to_string('email/user_warning.txt', {'user': user})
    html_msg = render_to_string('email/user_warning.html', {'user': user, 'domain': current_site.domain})

    send_mail(subject, message, 'admin@variantValidator.org', [user.email], html_message=html_msg)


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


def get_ucsc_link(validator, output):

    try:
        if output['genome'] == 'GRCh37':
            ucsc_assembly = 'hg19'
        else:
            ucsc_assembly = 'hg38'

        hgvs_genomic = validator.hp.parse_hgvs_variant(
            output['results'][0]['primary_assembly_loci'][ucsc_assembly]['hgvs_genomic_description'])

        chromosome = to_chr_num_ucsc(hgvs_genomic.ac, ucsc_assembly)
        vcf_varsome = output['results'][0]['primary_assembly_loci'][ucsc_assembly]['vcfstr_alt']

        if chromosome is not None:
            vcf_components = output['genomes'][ucsc_assembly].split('-')
            vcf_components[0] = chromosome
            if len(vcf_components[2]) > 10:
                vcf_components[2] = "<ref_bases>"
            if len(vcf_components[3]) > 10:
                vcf_components[3] = "<alt_bases>"
            vcf_varsome = '-'.join(vcf_components)

        browser_start = str(hgvs_genomic.posedit.pos.start.base - 11)
        browser_end = str(hgvs_genomic.posedit.pos.end.base + 11)
        ucsc_browser_position = '%s:%s-%s' % (chromosome, browser_start, browser_end)
        coding = output['results'][0]['hgvs_transcript_variant']
        if coding == "":
            coding = "intergenic"
        current_site = Site.objects.get_current()
        ucsc_link = 'http://genome.ucsc.edu/cgi-bin/hgTracks?' \
                    'db=%s&position=%s&hgt.customText=http://%s/bed/?variant=%s|%s|%s|%s|%s' % \
                    (
                     ucsc_assembly,
                     ucsc_browser_position,
                     current_site.domain,
                     coding,
                     hgvs_genomic.ac,
                     output['genome'],
                     valstr(hgvs_genomic),
                     vcf_varsome
                    )
        return ucsc_link
    except Exception:
        # This exception picks up variants with no primary assembly for the selected genome e.g. HLA-DRB4
        pass


def get_varsome_link(output):
    try:
        if output['genome'] == 'GRCh37':
            assembly = 'hg19'
        else:
            assembly = 'hg38'

        vcf = output['results'][0]['primary_assembly_loci'][assembly]['vcfstr_alt']
        link = f"https://varsome.com/variant/{assembly}/{vcf}"
        return link
    except Exception:
        # This exception picks up variants with no primary assembly for the selected genome e.g. HLA-DRB4
        pass


def get_gnomad_link(output):
    try:
        if output['genome'] == 'GRCh37':
            vcf = output['results'][0]['primary_assembly_loci']['grch37']['vcfstr_alt']
            link = f"https://gnomad.broadinstitute.org/variant/{vcf}"
            return link
    except Exception:
        # This exception picks up variants with no primary assembly for the selected genome e.g. HLA-DRB4
        pass
    try:
        if output['genome'] == 'GRCh38':
            vcf = output['results'][0]['primary_assembly_loci']['grch38']['vcfstr_alt']
            link = f"https://gnomad.broadinstitute.org/variant/{vcf}?dataset=gnomad_r3"
            return link
    except Exception:
        # This exception picks up variants with no primary assembly for the selected genome e.g. HLA-DRB4
        pass


def create_bed_file(validator, variant, chromosome, build, genomic, vcf, version):

    # Create local normalizer
    hn = normalizer.Normalizer(validator.hdp,
                               cross_boundaries=False,
                               shuffle_direction=3,
                               alt_aln_method=validator.alt_aln_method
                               )
    # In URL, + is translated to ' '
    if version != "":
        variant = version.replace(' ', '+')

    c_genome_pos = None
    if variant == 'intergenic':
        hgvs_coding = variant
    else:
        try:
            hgvs_coding = validator.hp.parse_hgvs_variant(variant)
            c_genome_pos = validator.myvm_t_to_g(hgvs_coding, chromosome, validator.vm, hn)
        except Exception as e:
            hgvs_coding = 'false'

    # Extract the additional data
    g_genome_pos = validator.hp.parse_hgvs_variant(genomic)
    vcf_list = vcf.split('-')

    # Create a header
    if build == 'GRCh37':
        ucsc_build = 'hg19'
    else:
        ucsc_build = 'hg38'
    # Create the request URL
    current_site = Site.objects.get_current()
    validate_url = reverse('validate')
    request_url = f'http://{current_site.domain}{validate_url}?variant={hgvs_coding}&genomebuild={build}'

    header = 'track name="VariantValidator" url="%s" db="%s" ' \
             'visibility="pack" color="67,0,255" description="VariantValidator track for %s"' % (
              request_url, ucsc_build, str(hgvs_coding))
    bed_list = [header]

    # Obtain orientation
    if hgvs_coding == 'intergenic':
        orientation = '+'
    else:
        try:
            ori = validator.tx_exons(tx_ac=hgvs_coding.ac, alt_ac=chromosome, alt_aln_method='splign')
        except Exception:
            pass
        try:
            orientation = int(ori[0]['alt_strand'])
        except UnboundLocalError:
            orientation = "."
        if orientation == -1:
            orientation = '-'
        else:
            orientation = '+'

    # Create the bed_call
    # map the c. variant
    if hgvs_coding != 'intergenic' and hgvs_coding != 'false':
        chr = to_chr_num_ucsc(c_genome_pos.ac, ucsc_build)
        start = str(c_genome_pos.posedit.pos.start.base - 1)
        end = str(c_genome_pos.posedit.pos.end.base)
        edit = str(hgvs_coding)
        c_bed_call = '\t'.join([chr, start, end, edit, '0', str(orientation)])
        bed_list.append(c_bed_call)

    # map the g. variant
    chr = to_chr_num_ucsc(g_genome_pos.ac, ucsc_build)
    start = str(g_genome_pos.posedit.pos.start.base - 1)
    end = str(g_genome_pos.posedit.pos.end.base)
    edit = str(g_genome_pos)
    g_bed_call = '\t'.join([chr, start, end, edit, '0', '+'])
    bed_list.append(g_bed_call)
    # map the vcf
    if 'chr' not in vcf_list[0]:
        chr = 'chr' + vcf_list[0]
    else:
        chr = vcf_list[0]
    start = str(int(vcf_list[1]) - 1)
    end = str(int(vcf_list[1]) + len(vcf_list[2]) - 1)
    edit = vcf
    v_bed_call = '\t'.join([chr, start, end, edit, '0', '+'])
    bed_list.append(v_bed_call)

    # Create output
    bed_call = '\n'.join(bed_list)
    bed_call = bed_call + '\n'
    return bed_call

# <LICENSE>
# Copyright (C) 2016-2025 VariantValidator Contributors
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
