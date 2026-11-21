# Sprintz residual backend on PTB-XL development records

The original 12-channel Sprintz FIRE/XFF + RLE 16-bit encoder produced 1,262,694 bytes on direct ADC input and 1,020,652 bytes after the fixed limb transform. The transformed stream exceeded the independently re-encoded 870,339-byte FLAC control by 150,313 bytes and the 783,305-byte target by 237,347 bytes. These results cover the 32 records identified by ADC hash in the parent study.

Each record is a standalone stream with one transform selector byte followed by the native Sprintz stream including metadata. Samples are interleaved in source order and mapped modulo 65536. Decode runs in a fresh process using the serialized payload. Limb reconstruction uses decoded I and II, followed by reduction to the original signed ADC width. Both representations recovered all 1,920,000 samples byte for byte.

The upstream encoder returns a count in 16-bit words even when its byte cursor ends on an odd boundary. Serializing only twice the reported count failed exact recovery. The wrapper conservatively includes one additional byte on every record, charged in full. Use the wrapper only with locally generated study streams.

Replay from this directory on little-endian AVX2/BMI2 x86 with the parent study's Python dependencies and the development cache. The source is the [authors' implementation](https://github.com/dblalock/sprintz/tree/a056cdb67d049669875ab5487359aca99ae873ea).

~~~bash
git clone https://github.com/dblalock/sprintz /tmp/sprintz-source
git -C /tmp/sprintz-source checkout a056cdb67d049669875ab5487359aca99ae873ea
s=/tmp/sprintz-source/cpp/Compress
g++ -O2 -fno-strict-aliasing -march=native -include cstring -I"$s" codec.cpp "$s"/{sprintz_xff_rle,format}.cpp -o /tmp/sprintz-study
python measure.py /tmp/clara-ecg-leads-pr1/cache /tmp/sprintz-study > /tmp/sprintz-replay.json
diff results.json /tmp/sprintz-replay.json
~~~
