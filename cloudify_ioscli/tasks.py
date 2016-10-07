########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.


from cloudify import ctx
from cloudify import exceptions as cfy_exc
from cloudify.decorators import operation
import ioscli_connection

@operation
def run(**kwargs):
    """main entry point for all calls"""

    calls = kwargs.get('calls', [])
    if not calls:
        ctx.logger.info("No calls")
        return

    # credentials
    properties = ctx.node.properties
    ioscli_auth = properties.get('ioscli_auth', {})
    ioscli_auth.update(kwargs.get('ioscli_auth', {}))
    ip = ioscli_auth.get('ip')
    user = ioscli_auth.get('user')
    password = ioscli_auth.get('password')
    key_content = ioscli_auth.get('key_content')
    port = ioscli_auth.get('port', 22)
    if not ip or not user or (not password and not key_content):
        raise cfy_exc.NonRecoverableError(
            "please check your credentials"
        )

    connection = ioscli_connection.connection()

    prompt = connection.connect(ip, user, password, key_content, port)

    ctx.logger.info("device prompt: " + prompt)

    for call in calls:
        operation = call.get('action', "")
        ctx.logger.info("Execute: " + operation)
        result = connection.run(operation)
        ctx.logger.info("Result of execution: " + result)
        # save results to runtime properties
        save_to = call.get('save_to')
        if save_to:
            ctx.instance.runtime_properties[save_to] = result

    while not connection.is_closed():
        ctx.logger.info("Execute close")
        result = connection.run("exit")
        ctx.logger.info("Result of close: " + result)

    connection.close()
