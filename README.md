# opentelemetry-exporter-python
The honeycomb.io Python exporter for OpenTelemetry

test

### Install

```bash
pip install opentelemetry-ext-honeycomb
```

### Initialize

```python
from opentelemetry import trace
from opentelemetry.ext.honeycomb import HoneycombSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchExportSpanProcessor

trace.set_tracer_provider(TracerProvider())
exporter = HoneycombSpanExporter(
    service_name="test-service",
    writekey=<HONEYCOMB_API_KEY>,
    dataset=<HONEYCOMB_DATASET>,
)

trace.get_tracer_provider().add_span_processor(BatchExportSpanProcessor(exporter))

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span('span_one'):
    with tracer.start_as_current_span('span_two'):
        with tracer.start_as_current_span('span_three'):
            print("Hello, from a child span")
```

### Development

This package uses [poetry](https://python-poetry.org/) for packaging and dependency management. To install a development copy into a virtualenv locally, run:

```
$ poetry install
```

And then activate the appropriate virtualenv.
