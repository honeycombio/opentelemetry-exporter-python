# Copyright 2020, Hound Technology Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


'''The honeycomb.io OpenTelemetry exporter uses libhoney to send events to
Honeycomb from within your Python application.
'''

import datetime
import json
import libhoney
import os
import socket
import sys
import types

from requests import Session

import opentelemetry.trace as trace_api
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace.status import StatusCode

VERSION = '0.16b0'
USER_AGENT_ADDITION = 'opentelemetry-exporter-python/%s' % VERSION


class HoneycombSpanExporter(SpanExporter):
    """Honeycomb span exporter for Opentelemetry.
    """
    def __init__(self, writekey='', dataset='', service_name='',
                 api_host='https://api.honeycomb.io'):
        if not writekey:
            writekey = os.environ.get('HONEYCOMB_WRITEKEY', '')

        if not dataset:
            dataset = os.environ.get('HONEYCOMB_DATASET', '')

        if not service_name:
            service_name = os.environ.get('HONEYCOMB_SERVICE', dataset)

        transmission_impl = libhoney.transmission.Transmission(
            user_agent_addition=USER_AGENT_ADDITION,
        )

        # Check for opentel instrumentation and unwrap Session request and send
        for func in ['request', 'send']:
            session_func = getattr(Session, func,  None)
            if getattr(session_func, "opentelemetry_instrumentation_requests_applied", False):
                session_func = session_func.__wrapped__  # pylint:disable=no-member

            # Bind session function for this object to the non-instrumented version.
            setattr(transmission_impl.session, func, types.MethodType(session_func, transmission_impl.session))

        self.client = libhoney.Client(
            writekey=writekey,
            dataset=dataset,
            api_host=api_host,
            transmission_impl=transmission_impl,
        )
        self.client.add_field('service_name', service_name)
        self.client.add_field('meta.otel_exporter_version', VERSION)
        self.client.add_field('meta.local_hostname', socket.gethostname())

    def export(self, spans):
        hny_data = _translate_to_hny(spans)
        for d in hny_data:
            e = libhoney.Event(data=d, client=self.client)
            e.created_at = d['start_time']
            del d['start_time']
            e.send()
        return SpanExportResult.SUCCESS

    def shutdown(self):
        self.client.flush()
        self.client.close()
        self.client = None


class HoneycombConsoleSpanExporter(SpanExporter):
    """Honeycomb console span exporter for the Honeycomb AWS Lambda Instrumentation.
    """

    def __init__(
        self,
        service_name=None,
        out=sys.stdout,
        formatter=lambda d: json.dumps(d) + os.linesep,
    ):
        self.out = out
        self.formatter = formatter
        self.service_name = service_name

    def export(self, spans):
        for d in _translate_to_hny(spans):
            del d["start_time"]  # trust API log timestamp?
            self.out.write(self.formatter(d))
        self.out.flush()
        return SpanExportResult.SUCCESS


def _translate_to_hny(spans):
    hny_data = []
    for span in spans:
        ctx = span.get_span_context()
        trace_id = ctx.trace_id
        span_id = ctx.span_id
        duration_ns = span.end_time - span.start_time
        d = {
            'trace.trace_id': trace_api.format_trace_id(trace_id)[2:],
            'trace.span_id': trace_api.format_span_id(span_id)[2:],
            'name': span.name,
            'start_time': datetime.datetime.utcfromtimestamp(span.start_time / float(1e9)),
            'duration_ms': duration_ns / float(1e6),  # nanoseconds to ms
            'response.status_code': span.status.status_code.value,
            'status.message': span.status.description,
            'span.kind': span.kind.name,  # meta.span_type?
        }
        if isinstance(span.parent, trace_api.Span):
            d['trace.parent_id'] = trace_api.format_span_id(span.parent.get_span_context().span_id)[2:]
        elif isinstance(span.parent, trace_api.SpanContext):
            d['trace.parent_id'] = trace_api.format_span_id(span.parent.span_id)[2:]
        # TODO: use sampling_decision attributes for sample rate.
        d.update(span.resource.attributes)
        d.update(span.attributes)

        # Ensure that if Status.Code is not OK, that we set the 'error' tag on the Jaeger span.
        if span.status.status_code is not StatusCode.OK:
            d['error'] = True
        hny_data.extend(_extract_refs_from_span(span))
        hny_data.extend(_extract_logs_from_span(span))
        hny_data.append(d)
    return hny_data


def _extract_refs_from_span(span):
    refs = []

    ctx = span.get_span_context()
    trace_id = ctx.trace_id
    p_span_id = ctx.span_id
    for link in span.links:
        l_trace_id = link.context.trace_id
        l_span_id = link.context.span_id
        ref = {
            'trace.trace_id': trace_api.format_trace_id(trace_id)[2:],
            'trace.parent_id': trace_api.format_span_id(p_span_id)[2:],
            'trace.link.trace_id': trace_api.format_trace_id(l_trace_id)[2:],
            'trace.link.span_id': trace_api.format_span_id(l_span_id)[2:],
            'meta.annotation_type': 'link',
            'ref_type': 0,
        }
        ref.update(link.attributes)
        refs.append(ref)
    return refs


def _extract_logs_from_span(span):
    logs = []

    ctx = span.get_span_context()
    trace_id = ctx.trace_id
    p_span_id = ctx.span_id
    for event in span.events:
        ev = {
            'start_time': datetime.datetime.utcfromtimestamp(event.timestamp / float(1e9)),
            'duration_ms': 0,
            'name': event.name,
            'trace.trace_id': trace_api.format_trace_id(trace_id)[2:],
            'trace.parent_id': trace_api.format_span_id(p_span_id)[2:],
            'meta.annotation_type': 'span_event',
        }
        ev.update(event.attributes)
        logs.append(ev)
    return logs
