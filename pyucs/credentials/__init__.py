import os
import requests
import json
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from pycrypt.encryption import Encryption, AESCipher


class Credential:

    def __init__(self, username):
        self.username = username
        self.session = requests.Session()
        self.session.verify = False
        disable_warnings(InsecureRequestWarning)
        self.__password = None
        self.__private_file = os.environ.get('RSAPrivateFile' or None)
        self.__secret = open(os.environ.get('RSASecret' or None), 'r').read()

    def get_credential(self, dev=False):
        if dev:
            credstore_uri = 'https://credstore-dev/credentialstore/GetCredential?ClientId={}&username={}'.format(
                os.environ['ClientId'],
                self.username
            )
        else:
            credstore_uri = 'https://credstore/credentialstore/GetCredential?ClientId={}&username={}'.format(
                os.environ['ClientId'],
                self.username
            )

        response = self.session.get(url=credstore_uri)
        data = json.loads(response.text)
        self.decipher(
            shared_key=data[0].get('secret' or None)[0].get('shared_key' or None),
            password=data[0].get('secret' or None)[0].get('password' or None)
        )

        return {
            'username': self.username,
            'password': self.__password
        }

    def decipher(self, shared_key, password):
        aes_cipher = AESCipher()
        rsa_cipher = Encryption()

        rsa_cipher.decrypt(encrypted_data=shared_key, private_key_file=self.__private_file, secret_code=self.__secret)
        self.__password = aes_cipher.decrypt(enc=password, key=rsa_cipher.get_decrypted_message())
        self.__secret = None
