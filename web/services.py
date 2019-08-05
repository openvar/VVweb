
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
    counter = 0
    for k, v in val.items():
        if k == 'flag' or k == 'metadata':
            continue
        print(k)
        counter += 1
        input_str = v['submitted_variant']
        v['id'] = 'res' + str(counter)
        tx_id_info = validator.hdp.get_tx_identity_info(v['hgvs_transcript_variant'].split(':')[0])
        print(tx_id_info)
        gene_info = validator.hdp.get_gene_info(v['gene_symbol'])
        print(gene_info)
        v['chr_loc'] = gene_info[1]
        tx_ac = v['hgvs_transcript_variant'].split(':')[0]
        gene_ac = v['hgvs_refseqgene_variant'].split(':')[0]
        prot_ac = v['hgvs_predicted_protein_consequence']['tlr'].split(':')[0]
        prot_ac = prot_ac.split('(')[0]
        v['tx_ac'] = tx_ac
        v['gene_ac'] = gene_ac
        v['prot_ac'] = prot_ac
        acc = tx_ac.split('.')
        version_number = int(acc[1])
        accession = acc[0]
        latest = True
        for trans in list(val.keys()):
            if accession in trans and trans != k:
                other_version = int(trans.split(':')[0].split('.')[1])
                if other_version > version_number:
                    latest = False
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
            v['primary_assembly_loci'][genome]['vcfstr'] = vcfstr
            v['primary_assembly_loci'][genome]['vcfstr_alt'] = "%s-%s-%s-%s" % (
                vcfdict['chr'], vcfdict['pos'], vcfdict['ref'], vcfdict['alt'])
            v['primary_assembly_loci'][genome]['ac'] = \
                v['primary_assembly_loci'][genome]['hgvs_genomic_description'].split(':')[0]
        each.append(v)

    alloutputs = {
        'flag': flag,
        'meta': meta,
        'inputted': input_str,
        'results': sorted(each, key=lambda i: i['tx_ac']),
    }

    return alloutputs
