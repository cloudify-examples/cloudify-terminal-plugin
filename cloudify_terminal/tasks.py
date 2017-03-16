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
from jinja2 import Template

import terminal_connection


@operation
def run(**kwargs):
    """main entry point for all calls"""

    calls = kwargs.get('calls', [])
    if not calls:
        ctx.logger.info("No calls")
        return

    # credentials
    properties = ctx.node.properties
    terminal_auth = properties.get('terminal_auth', {})
    terminal_auth.update(kwargs.get('terminal_auth', {}))
    ip = terminal_auth.get('ip')
    user = terminal_auth.get('user')
    password = terminal_auth.get('password')
    key_content = terminal_auth.get('key_content')
    promt_check = terminal_auth.get('promt_check')
    error_examples = terminal_auth.get('errors')
    port = terminal_auth.get('port', 22)
    if not ip or not user or (not password and not key_content):
        raise cfy_exc.NonRecoverableError(
            "please check your credentials"
        )

    connection = terminal_connection.connection()

    prompt = connection.connect(ip, user, password, key_content, port,
                                promt_check)

    ctx.logger.info("device prompt: " + prompt)

    for call in calls:
        # use action if exist
        operation = call.get('action', "")
        # use template if have
        if not operation and 'template' in call:
            template_name = call.get('template')
            template_params = call.get('params')
            template = ctx.get_resource(template_name)
            if not template:
                ctx.logger.info("Empty template.")
                continue
            template_engine = Template(template)
            if template_params:
                operation = template_engine.render(template_params)
            else:
                operation = template_engine.render({})
        if not operation:
            continue
        result = ""
        for op_line in operation.split("\n"):
            ctx.logger.info("Execute: " + op_line)
            result += connection.run(op_line, promt_check, error_examples)
        ctx.logger.info("Result of execution: " + result)
        # save results to runtime properties
        save_to = call.get('save_to')
        if save_to:
            ctx.instance.runtime_properties[save_to] = result

    while not connection.is_closed():
        ctx.logger.info("Execute close")
        result = connection.run("exit", promt_check, error_examples)
        ctx.logger.info("Result of close: " + result)

    connection.close()
