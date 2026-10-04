"""The v6 case families. One module per behaviour of `contracts.BEHAVIOURS`
that v6 authors anew; `common6.py` is what every one of them shares.

v6 MIRRORS v5, it does not replace it: the v6 builder composes a v5
`CaseBuilderV5` (`scenarios5/common.py`), adds the `CaseV6Meta` axis and the
`gen_v6` value mint, and leaves every v5 declaration and baseline untouched.
`single` is not authored here either — the revised v4 corpus supplies it, and a
family written twice is a share that stops being a measurement.
"""
