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

if __name__ == '__main__':
    unittest.main()