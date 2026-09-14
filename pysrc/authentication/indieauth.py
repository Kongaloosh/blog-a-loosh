"""
    This module is a collection of methods related to authentication and indieAuth.s
"""

__author__ = 'alex'

import requests


def checkAccessToken(access_token, client_id):
    """
        We check with indie-auth to make sure the token is valid
    """
    r = requests.get(url='https://tokens.indieauth.com/token', headers={'Authorization': 'Bearer '+access_token}, timeout=(5, 15))
    return r.status_code == requests.codes.ok

