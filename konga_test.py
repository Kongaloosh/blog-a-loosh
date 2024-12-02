import os
import kongaloosh as kgl
import unittest
import tempfile

class KongaTestCase(unittest.TestCase):

    def setUp(self):
        """Actions taken to setup fil"""
        self.db_fd, kgl.app.config['DATABASE'] = tempfile.mkstemp()
        kgl.app.config['TESTING'] = True
        self.app = kgl.app.test_client()
        with kgl.app.app_context():
            kgl.init_db()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(kgl.app.config['DATABASE'])


    def test_login(self):
        # make sure the credentials are right and that it re-directs where it should
        pass

    def test_logout(self):
        pass

    def test_micropub_post(self):
        pass

    def test_drafts(self):
        pass

    def test_add(self):
        # if not logged in, abort
        # if logged in...
        #   do we make drafts at the right time
        #   do we check for the location with the right values
        #   do reply-tos get properly formatted
        #   does the syndication format properly and return values to a
        #   do redirects function in the right way
        pass

    def test_add(self):
        # if not logged in, abort
        # if logged in...
        #   do we make drafts at the right time
        #   do we check for the location with the right values
        #   do reply-tos get properly formatted
        #   does the syndication format properly and return values to a
        #   do redirects function in the right way
        pass

if __name__ == '__main__':
    unittest.main()