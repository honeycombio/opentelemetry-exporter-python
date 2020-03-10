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

import libhoney
import os
import socket

import opentelemetry.trace as trace_api
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace.status import StatusCanonicalCode

from honeycomb.version import VERSION

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

        self.client = libhoney.Client(
            writekey=writekey,
            dataset=dataset,
            api_host=dataset,
            user_agent_addition=USER_AGENT_ADDITION,
        )
        self.client.add_field('service_name', service_name)
        self.client.add_field('meta.otel_exporter_version', VERSION)
        self.client.add_field('meta.local_hostname', socket.gethostname())

    def export(self, spans):
        hny_data = _translate_to_hny(spans)
        for d in hny_data:
            e = libhoney.Event(data=d, client=self.client)
            e.send()
        return SpanExportResult.SUCCESS

    def shutdown(self):
        self.client.flush()
        self.client.close()
        self.client = None

def _translate_to_hny(spans):
    hny_data = []
    for span in spans:
        ctx = span.get_context()
        trace_id = ctx.trace_id
        span_id = ctx.span_id
        if isinstance(span.parent, trace_api.Span):
            parent_id = span.parent.get_context().span_id
        elif isinstance(span.parent, trace_api.SpanContext):
            parent_id = span.parent.span_id
        duration = span.end_time - span.start_time
        d = {
            'trace.trace_id': trace_id,
            'trace.parent_id': parent_id,
            'trace.span_id': span_id,
            'name': span.name,
            'start_time': span.start_time,
            'duration_ms': duration.total_seconds() * 1000.0,
            'response.status_code': span.status.canonical_code.value,
            'status.message': span.status.description,
            'span.kind': span.kind.name,  # meta.span_type?
        }
        # TODO: use sampling_decision attributes for sample rate.
        d.update(span.attributes)

        # Ensure that if Status.Code is not OK, that we set the 'error' tag on the Jaeger span.
        if span.status.canonical_code is not StatusCanonicalCode.OK:
            d['error'] = True
        hny_data.extend(_extract_refs_from_span(span))
        hny_data.extend(_extract_logs_from_span(span))
        hny_data.append(d)
    return hny_data

def _extract_refs_from_span(span):
    refs = []

    ctx = span.get_context()
    trace_id = ctx.trace_id
    p_span_id = ctx.span_id
    for link in span.links:
        l_trace_id = link.context.trace_id
        l_span_id = link.context.span_id
        ref = {
            'trace.trace_id': trace_id,
            'trace.parent_id': p_span_id,
            'trace.link.trace_id': l_trace_id,
            'trace.link.span_id': l_span_id,
            'meta.span_type': 'link',
            'ref_type': 0,
        }
        ref.update(link.attributes)
        refs.append(ref)
    return refs

def _extract_logs_from_span(span):
    logs = []

    ctx = span.get_context()
    trace_id = ctx.trace_id
    p_span_id = ctx.span_id
    for event in span.events:
        l = {
            'start_time': event.timestamp,
            'duration_ms': 0,
            'name': event.name,
            'trace.trace_id': trace_id,
            'trace.parent_id': p_span_id,
            'meta.span_type': 'span_event',
        }
        l.update(event.attributes)
        logs.append(l)
    return logs
