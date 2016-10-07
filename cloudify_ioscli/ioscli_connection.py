# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import paramiko
from StringIO import StringIO
from cloudify import exceptions as cfy_exc

class connection(object):

    # ssh connection
    ssh = None
    conn = None

    # buffer for same packages, will save partial packages between calls
    buff = ""

    def connect(
        self, ip, user, password=None, key_content=None, port=22
    ):
        """open connection"""
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if key_content:
            key = paramiko.RSAKey.from_private_key(
                StringIO(key_content)
            )
            self.ssh.connect(
                ip, username=user, pkey=key, port=port, timeout=5, allow_agent=False
            )
        else:
            self.ssh.connect(
                ip, username=user, password=password, port=port, timeout=5, allow_agent=False, look_for_keys=False
            )

        self.conn = self.ssh.invoke_shell()
        buff = ""

        while self.buff.find("#") == -1 and self.buff.find("$") == -1:
            self.buff += self.conn.recv(128)

        self.hostname = ""
        #looks as we have some hostname
        for code in ["#", "$"]:
            if self.buff.find(code) != -1:
                self.hostname = self.buff[:self.buff.find(code)].strip()
                self.buff = self.buff[self.buff.find(code) + 1:]
        return self.hostname

    def __clenup_response(self, text, prefix):
        text = text.strip()
        if text[:len(prefix)] != prefix:
            raise cfy_exc.NonRecoverableError(
                "We dont have prefix '%s' in response: %s" % (prefix, text)
            )
        response = text[len(prefix):].strip()
        if response[:2] == "% ":
            raise cfy_exc.NonRecoverableError(
                "Looks as we have error in response: %s" % (prefix, response)
            )
        return response

    def run(self, command):
        response_prefix = command.strip()
        self.conn.send(response_prefix + "\n")

        if self.conn.closed:
            return ""

        have_prompt = False

        message_from_server = ""

        while not have_prompt:
            while self.buff.find("\n") == -1 and self.buff.find("#") == -1 and self.buff.find("$") == -1:
                self.buff += self.conn.recv(128)
                if self.conn.closed:
                    return self.__clenup_response(message_from_server, response_prefix)

            while self.buff.find("\n") != -1:
                line = self.buff[:self.buff.find("\n") + 1]
                self.buff = self.buff[self.buff.find("\n") + 1 :]
                message_from_server += line

            # last line without new line at the end
            if "#" in self.buff:
                have_prompt = True
                self.hostname = self.buff[:self.buff.find("#")]
                self.buff = self.buff[self.buff.find("#") + 1 :]

            if self.conn.closed:
                return self.__clenup_response(message_from_server, response_prefix)

        return self.__clenup_response(message_from_server, response_prefix)

    def is_closed(self):
        if self.conn:
            return self.conn.closed
        return True

    def close(self):
        """close connection"""
        try:
            # sometime code can't close in time
            self.conn.close()
        finally:
            self.ssh.close()
