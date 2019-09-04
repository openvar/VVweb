from django.test import TestCase
import VariantValidator
from web.services import process_result


class TestProcessResultService(TestCase):

    def setUp(self):
        self.vv = VariantValidator.Validator()

    def test_empty(self):
        val = self.vv.validate('', 'GRCh37', 'all').format_as_dict()
        res = process_result(val, self.vv)
        print(res)
        self.assertEqual(list(res.keys()), ['flag', 'meta', 'inputted', 'genomes', 'results'])
        self.assertEqual(res['flag'], 'warning')
        self.assertEqual(res['inputted'], '')
        self.assertEqual(res['results'], [])
        self.assertEqual(res['genomes'], {})

    def test_simple_okay(self):
        val = self.vv.validate('NM_000088.3:c.589G>T', 'GRCh37', 'all').format_as_dict()
        res = process_result(val, self.vv)
        print(res)
        self.assertEqual(list(res.keys()), ['flag', 'meta', 'inputted', 'genomes', 'results'])
        self.assertEqual(res['flag'], 'gene_variant')
        self.assertEqual(res['inputted'], 'NM_000088.3:c.589G>T')
        self.assertEqual(len(res['results']), 1)
        self.assertEqual(res['genomes'], {'grch37': '17-48275363-C-A', 'hg19': 'chr17-48275363-C-A',
                                          'grch38': '17-50198002-C-A', 'hg38': 'chr17-50198002-C-A'})
        self.assertEqual(res['results'][0]['gene_symbol'], 'COL1A1')
        self.assertEqual(res['results'][0]['latest'], True)

    def test_multiple_variants(self):
        val = self.vv.validate('12-111064166-G-A', 'GRCh37', 'all').format_as_dict()
        res = process_result(val, self.vv)
        print(res)
        self.assertEqual(list(res.keys()), ['flag', 'meta', 'inputted', 'genomes', 'results'])
        self.assertEqual(res['flag'], 'gene_variant')
        self.assertEqual(res['inputted'], '12-111064166-G-A')
        self.assertEqual(len(res['results']), 10)
        self.assertEqual(res['results'][2]['tx_ac'], 'NM_001173975.1')
        self.assertFalse(res['results'][2]['latest'])
        self.assertEqual(res['results'][3]['tx_ac'], 'NM_001173975.2')
        self.assertTrue(res['results'][3]['latest'])



