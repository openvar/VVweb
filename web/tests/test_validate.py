from django.test import TestCase
from unittest import TestCase as UnitTestCase
import VariantValidator
from web.services import process_result


class TestProcessResultService(UnitTestCase):

    @classmethod
    def setUpClass(cls):
        cls.vv = VariantValidator.Validator()

    def test_empty(self):
        val = self.vv.validate('', 'GRCh37', 'all').format_as_dict()
        res = process_result(val, self.vv)
        self.assertEqual(list(res.keys()), ['flag', 'meta', 'inputted', 'genomes', 'results', 'warnings'])
        self.assertEqual(res['flag'], 'warning')
        self.assertEqual(res['inputted'], '')
        self.assertEqual(res['results'], [])
        self.assertEqual(res['genomes'], {})
        self.assertEqual(res['warnings'], ['Variant description  is not in an accepted format'])

    def test_simple_okay(self):
        val = self.vv.validate('NM_000088.3:c.589G>T', 'GRCh37', 'all').format_as_dict()
        res = process_result(val, self.vv)
        self.assertEqual(list(res.keys()), ['flag', 'meta', 'inputted', 'genomes', 'results', 'warnings'])
        self.assertEqual(res['flag'], 'gene_variant')
        self.assertEqual(res['inputted'], 'NM_000088.3:c.589G>T')
        self.assertEqual(len(res['results']), 1)
        self.assertEqual(res['genomes'], {'grch37': '17-48275363-C-A', 'hg19': 'chr17-48275363-C-A',
                                          'grch38': '17-50198002-C-A', 'hg38': 'chr17-50198002-C-A'})
        self.assertEqual(res['results'][0]['gene_symbol'], 'COL1A1')
        self.assertEqual(res['results'][0]['latest'], True)
        self.assertEqual(res['warnings'], [])

    def test_multiple_variants(self):
        val = self.vv.validate('12-111064166-G-A', 'GRCh37', 'all').format_as_dict()
        res = process_result(val, self.vv)
        self.assertEqual(list(res.keys()), ['flag', 'meta', 'inputted', 'genomes', 'results', 'warnings'])
        self.assertEqual(res['flag'], 'gene_variant')
        self.assertEqual(res['inputted'], '12-111064166-G-A')
        self.assertEqual(len(res['results']), 10)
        self.assertEqual(res['results'][2]['tx_ac'], 'NM_001173975.1')
        self.assertFalse(res['results'][2]['latest'])
        self.assertEqual(res['results'][3]['tx_ac'], 'NM_001173975.2')
        self.assertTrue(res['results'][3]['latest'])
        self.assertTrue(len(res['genomes']), 4)
        self.assertEqual(res['warnings'], [])

    def test_intergenic(self):
        val = self.vv.validate('19-15311794-A-G', 'GRCh37', 'all').format_as_dict()
        res = process_result(val, self.vv)
        print(res)
        self.assertEqual(list(res.keys()), ['flag', 'meta', 'inputted', 'genomes', 'results', 'warnings'])
        self.assertEqual(res['flag'], 'intergenic')
        self.assertEqual(res['genomes'], {'grch37': '19-15311794-A-G', 'hg19': 'chr19-15311794-A-G',
                                          'grch38': '19-15200983-A-G', 'hg38': 'chr19-15200983-A-G'})
        self.assertEqual(len(res['results']), 1)
        self.assertEqual(res['results'][0]['gene_ac'], 'NG_009819.1')
        self.assertTrue(res['results'][0]['latest'])
        self.assertEqual(res['warnings'], [])
        self.assertEqual(res['results'][0]['safe_hgvs_trans'], 'Unknown transcript variant')

    def test_wrong_genome(self):
        val = self.vv.validate('17-50198002-C-A', 'GRCh37', 'all').format_as_dict()
        res = process_result(val, self.vv)
        print(res)
        self.assertEqual(list(res.keys()), ['flag', 'meta', 'inputted', 'genomes', 'results', 'warnings'])
        self.assertEqual(res['flag'], 'warning')
        self.assertEqual(res['warnings'], ['NC_000017.10:g.50198002C>A: '
                                           'Variant reference (C) does not agree with reference sequence (G)'])



