import unittest
from unittest.mock import Mock
from .common import LabError
from .custody import advertised_ref,confirm_publication

class NativeRefConfirmation(unittest.TestCase):
    def test_exact_git_protocol_destination_required(self):
        for response in ('a'*40+'\trefs/heads/other','not a git ref','a'*40+'\trefs/heads/probe\n'+'b'*40+'\trefs/heads/probe'):
            with self.subTest(response=response),self.assertRaises(LabError):advertised_ref(lambda *args:response,None,'probe')
        self.assertEqual(advertised_ref(lambda *args:'a'*40+'\trefs/heads/probe',None,'probe'),'a'*40)
    def test_delayed_parent_may_converge_without_second_write(self):
        read=Mock(side_effect=['a'*40,'a'*40,'b'*40]);pause=Mock()
        self.assertEqual(confirm_publication(read,'b'*40,'a'*40,pause=pause),'b'*40)
        self.assertEqual(read.call_count,3);self.assertEqual(pause.call_count,2)
    def test_unchanged_or_unexpected_ref_is_never_success(self):
        read=Mock(return_value='a'*40)
        with self.assertRaisesRegex(LabError,'DID_NOT_CONVERGE'):confirm_publication(read,'b'*40,'a'*40,pause=lambda _:None)
        self.assertEqual(read.call_count,5)
        read=Mock(return_value='c'*40)
        with self.assertRaisesRegex(LabError,'CONCURRENT_WRITER'):confirm_publication(read,'b'*40,'a'*40,pause=lambda _:None)
        self.assertEqual(read.call_count,1)

if __name__=='__main__':unittest.main()
