#noisemapper

    usage: noisemapper.py [-h] -n NAME_MAPPINGS -f FLOORPLAN -s SPICE
                          [--cycle-time CYCLE_TIME] [--rise-time RISE_TIME]
                          [--fall-time FALL_TIME]
                          [--current-scale-factor CURRENT_SCALE_FACTOR] -o OUT -p
                          POWERTRACE [-v] [--time-prefix TIME_PREFIX]
                          [--time-precision TIME_PRECISION]
                          [--amplitude-precision AMPLITUDE_PRECISION]

    The name mappings should be a JSON object of the form {"floorplan_name":
    "powertrace_name"}

    optional arguments:
      -h, --help            show this help message and exit
      -n NAME_MAPPINGS, --name-mappings NAME_MAPPINGS
      -f FLOORPLAN, --floorplan FLOORPLAN
      -s SPICE, --spice SPICE
      --cycle-time CYCLE_TIME
                            Defaults to 1.0
      --rise-time RISE_TIME
                            Defaults to 0.1
      --fall-time FALL_TIME
                            Defaults to 0.1
      --current-scale-factor CURRENT_SCALE_FACTOR
                            each peak amplitude wil be divided by csf, defaults to
                            1.0
      -o OUT, --out OUT
      -p POWERTRACE, --powertrace POWERTRACE
      -v, --verbose
      --time-prefix TIME_PREFIX
                            SI prefix for time units in the output, defaults to N
      --time-precision TIME_PRECISION
                            Number of decimal places to output for time values,
                            defaults to 1
      --amplitude-precision AMPLITUDE_PRECISION
                            Number of decimal places to output for amplitude
                            values, defaults to 4
