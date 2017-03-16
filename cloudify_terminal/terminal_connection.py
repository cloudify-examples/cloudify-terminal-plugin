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

DEFAULT_PROMT = ["#", "$"]


class connection(object):

    # ssh connection
    ssh = None
    conn = None

    # buffer for same packages, will save partial packages between calls
    buff = ""

    def __find_any_in(self, buff, promt_check):
        for code in promt_check:
            position = buff.find(code)
            if position != -1:
                return position
        # no promt codes
        return -1

    def connect(self, ip, user, password=None, key_content=None, port=22,
                prompt_check=None):
        """open connection"""
        if not prompt_check:
            prompt_check = DEFAULT_PROMT

        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if key_content:
            key = paramiko.RSAKey.from_private_key(
                StringIO(key_content)
            )
            self.ssh.connect(ip, username=user, pkey=key, port=port, timeout=5,
                             allow_agent=False)
        else:
            self.ssh.connect(ip, username=user, password=password, port=port,
                             timeout=5, allow_agent=False, look_for_keys=False)

        self.conn = self.ssh.invoke_shell()
        self.buff = ""

        while self.__find_any_in(self.buff, prompt_check) == -1:
            self.buff += self.conn.recv(128)

        self.hostname = ""
        #looks as we have some hostname
        code_position = self.__find_any_in(self.buff, prompt_check)
        if code_position != -1:
            self.hostname = self.buff[:code_position].strip()
            self.buff = self.buff[code_position + 1:]
        return self.hostname

    def __clenup_response(self, text, prefix, error_examples):
        if not error_examples:
            return

        text = text.strip()
        if text[:len(prefix)] != prefix:
            raise cfy_exc.NonRecoverableError(
                "We dont have prefix '%s' in response: %s" % (prefix, text)
            )
        response = text[len(prefix):].strip()
        # check for errors started only from new line
        errors_with_new_line = ["\n " + error for error in error_examples]
        if self.__find_any_in(response, errors_with_new_line) != -1:
            raise cfy_exc.NonRecoverableError(
                "Looks as we have error in response: %s" % (text)
            )
        return response

    def run(self, command, prompt_check=None, error_examples=None):
        if not prompt_check:
            prompt_check = DEFAULT_PROMT

        response_prefix = command.strip()
        self.conn.send(response_prefix + "\n")

        if self.conn.closed:
            return ""

        have_prompt = False

        message_from_server = ""

        while not have_prompt:
            while self.__find_any_in(self.buff, prompt_check + ["\n"]) == -1:
                self.buff += self.conn.recv(128)
                if self.conn.closed:
                    return self.__clenup_response(message_from_server,
                                                  response_prefix,
                                                  error_examples)

            while self.buff.find("\n") != -1:
                line = self.buff[:self.buff.find("\n") + 1]
                self.buff = self.buff[self.buff.find("\n") + 1:]
                message_from_server += line

            # last line without new line at the end
            code_position = self.__find_any_in(self.buff, prompt_check)
            if code_position != -1:
                have_prompt = True
                self.hostname = self.buff[:code_position]
                self.buff = self.buff[code_position + 1:]

            if self.conn.closed:
                return self.__clenup_response(message_from_server,
                                              response_prefix,
                                              error_examples)

        return self.__clenup_response(message_from_server,
                                      response_prefix,
                                      error_examples)

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
