#!/usr/bin/env python

import json
import csv
import re
import math
from pprint import pprint

CURRENT_SOURCE_PATTERN = re.compile('^i', re.I)
INDUCTOR_PATTERN = re.compile('^l', re.I)
PULSE_PATTERN = re.compile('^pulse', re.I)
POSITION_PATTERN = re.compile(r'\An|_n', re.I)

def get_PWLs(powertrace, fmt, cycletime, risetime, falltime, csf):
    '''
        Return a dictionary keyed by the columns powertrace. Each entry is a
        long string of the form PWL(t1 v1 t2 v2 ...) for the component.

        powertrace is a csv.DictReader
    '''
    result = dict()
    i = 0
    components = powertrace.fieldnames
    for c in components:
        result[c] = ['PWL(']

    for row in powertrace:
        cycle_start = cycletime * i
        peak = cycle_start + risetime
        cycle_end = peak + falltime
        for c in components:
            peak_amplitude = float(row[c]) / csf
            if math.isinf(peak_amplitude) or math.isnan(peak_amplitude):
                peak_amplitude = 0.0
            result[c].append(fmt % (cycle_start, peak, peak_amplitude, cycle_end))
        i = i + 1

    for c in components:
        # in case we don't hae any data for this component, set it to zero
        if len(result[c]) == 1:
            result[c].append('0 0')
        result[c][1] = result[c][1].strip()
        result[c].append(')')
        result[c] = ''.join(result[c])

    return result

def indexof_match(regex, l):
    '''
    Return the index of the first string in l that matches the compiled regex object
    '''
    for i in range(len(l)):
        if regex.match(l[i]): return i

def get_positions(e):
    '''
    Extract and return all (x,y) positions in the split line e

    This function is pretty liberal in what it will accept as a position specifier
    '''
    result = []
    for w in e:
        if POSITION_PATTERN.search(w):
            pos = w.split('_')[-2:]
            if len(pos) == 2:
                try:
                    result.append([float(x) for x in pos])
                except ValueError:
                    pass
    return result

def get_i_position(e):
    '''
    If e is a current source, return the parsed position
    e is a split line to check
    '''
    if e:
        i = indexof_match(POSITION_PATTERN, e)
        if i:
            return [float(x) for x in e[i].split('_')[1:]]

def get_l_positions(e):
    return [[float(x) for x in p] for p in [f.split('_')[-2:] for f in e[1:3]]]

def position_range(spice):
    '''
    For the split lines in spice, find the bounding box of the all points
    '''
    positions = []
    for e in spice:
        positions += get_positions(e)
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    return [[min(xs), max(xs)], [min(ys), max(ys)]]

def replace_current(e, s):
    '''
    Given the split list e containing a SPICE element, replace
    the amplitude with the given string s
    '''
    return e[:3] + [s]

def chop_pulse(e):
    '''
    If the split list e has a pulse, return everything preceding it
    '''
    pulse_index = indexof_match(PULSE_PATTERN, e)
    if pulse_index:
        return e[:pulse_index]

def floorplan_range(fp):
    '''
    Return a bounding box for the given floorplan
    '''
    xs = [e[0][0] for e in fp.values()] + [e[0][1] for e in fp.values()]
    ys = [e[1][0] for e in fp.values()] + [e[1][1] for e in fp.values()]
    return [[min(xs), max(xs)], [min(ys), max(ys)]]

def scale_floorplan(fp, box):
    '''
    Perform an in-place scaling of fp to fit box
    '''
    fp_box = floorplan_range(fp)
    for rec in fp.values():
        rec[0][0] = box[0][0] + (rec[0][0] - fp_box[0][0]) * (box[0][1] - box[0][0]) / (fp_box[0][1] - fp_box[0][0])
        rec[0][1] = box[0][0] + (rec[0][1] - fp_box[0][0]) * (box[0][1] - box[0][0]) / (fp_box[0][1] - fp_box[0][0])
        rec[1][0] = box[1][0] + (rec[1][0] - fp_box[1][0]) * (box[1][1] - box[1][0]) / (fp_box[1][1] - fp_box[1][0])
        rec[1][1] = box[1][0] + (rec[1][1] - fp_box[1][0]) * (box[1][1] - box[1][0]) / (fp_box[1][1] - fp_box[1][0])

def find_component(fp, pos):
    '''
    Find the component in floorplan fp (if any) that contains the point pos
    '''
    for component, rec in fp.items():
        if pos[0] >= rec[0][0] and pos[0] <= rec[0][1] and pos[1] >= rec[1][0] and pos[1] <= rec[1][1]:
            return component

def pop_worst(d):
    loser_value = max([e['distance'] for e in d.values()])
    for k,v in d.items():
        if v['distance'] == loser_value:
            loser = k
    return d.pop(loser)

def nearest_components(fp, pos, name, left, right, best, inductor_count):
    for component, rec in fp.items():
        if pos[0] >= rec[0][0] and pos[0] <= rec[0][1] and pos[1] >= rec[1][0] and pos[1] <= rec[1][1]:
            # we're inside a rectangle
            best[component][name] = {
                'left': left,
                'right': right,
                'distance': 0.0
            }
        else:
            distance = abs((rec[0][0] + rec[0][1])/2 - pos[0]) + abs((rec[1][0] + rec[1][1])/2 - pos[1])
            if len([k for k,v in best[component].items() if v['distance'] > 0.0]) < inductor_count:
                best[component][name] = {
                    'left': left,
                    'right': right,
                    'distance': distance
                }
            elif distance < max([b['distance'] for b in best[component].values()]):
                best[component][name] = {
                    'left': left,
                    'right': right,
                    'distance': distance
                }
                pop_worst(best[component])

def PWL_format(timeprefix, timeprec, aprec):
    '''
    Format strings generating format strings...
    '''
    return ' %%.%df%s 0 %%.%df%s %%.%df %%.%df%s 0' % (timeprec, timeprefix, timeprec, timeprefix, aprec, timeprec, timeprefix)


def translate_to_PWL(floorplan, powertrace, spice, inductor_count):
    '''
    Given a scaled floorplan fp, powertrace pt, and spice file sp, convert current
    sources to PWL representation using the given power data
    '''
    hit = 0
    miss = 0
    inductors = {'list': [], 'nearest': {}}
    for comp in floorplan.keys():
        inductors['nearest'][comp] = {}
    for i in range(len(spice)):
        if len(spice[i]) < 1:
            continue
        if CURRENT_SOURCE_PATTERN.match(spice[i][0]):
            pos = get_i_position(spice[i])
            if not pos:
                continue
            comp = find_component(floorplan, pos)
            if not comp:
                spice[i].insert(0, '*')
                miss += 1
                continue
            hit += 1
            spice[i] = replace_current(spice[i], powertrace[comp])
        elif INDUCTOR_PATTERN.match(spice[i][0]):
            inductors['list'].append(spice[i][0])
            pos = get_l_positions(spice[i])
            if not pos:
                continue
            nearest_components(floorplan, pos[0], spice[i][0], spice[i][1], spice[i][2], inductors['nearest'], inductor_count)
    print('\thit: %d\n\tmiss: %d' % (hit, miss))
    return inductors

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='The name mappings should be a JSON object of the form {"floorplan_name": "powertrace_name"}')
    parser.add_argument('-n', '--name-mappings', default='names.json', help='Defaults to names.json')
    parser.add_argument('-f', '--floorplan', default='floorplan.tsv', help='Defaults to floorplan.tsv')
    parser.add_argument('-s', '--spice', default='in.spice', help='Defaults to in.spice')
    parser.add_argument('--cycle-time', default=1.0, type=float, help='Defaults to 1.0')
    parser.add_argument('--rise-time', default=0.1, type=float, help='Defaults to 0.1')
    parser.add_argument('--fall-time', default=0.1, type=float, help='Defaults to 0.1')
    parser.add_argument('--current-scale-factor', default=1.0, help='each peak amplitude wil be divided by csf, defaults to 1.0')
    parser.add_argument('-o', '--out', default='out.spice', help='Defaults to out.spice')
    parser.add_argument('-l', '--inductors', default='inductors.json', help='Sets of nearest inductors for each component. Defaults to inductors.json')
    parser.add_argument('-p', '--powertrace', default='powertrace.csv', help='Defaults to powertrace.csv')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--time-prefix', default='N', help='SI prefix for time units in the output, defaults to N')
    parser.add_argument('--time-precision', default=1, type=int, help='Number of decimal places to output for time values, defaults to 1')
    parser.add_argument('--amplitude-precision', default=4, type=int, help='Number of decimal places to output for amplitude values, defaults to 4')
    parser.add_argument('--nearest-inductors', default=5, type=int, help='Number nearby inductors to report, defaults to 5')
    args = parser.parse_args()

    print('loading name mappings')
    with open(args.name_mappings) as f:
        name_mappings = json.load(f)

    floorplan = dict()
    print('loading floorplan')
    with open(args.floorplan, newline='') as f:
        d = csv.reader((row for row in f if not row.startswith('#')), delimiter='\t')
        for row in d:
            if row:
                try:
                    floorplan[name_mappings[row[0]]] = [
                        [float(row[3]), float(row[1]) + float(row[3])],
                        [float(row[4]), float(row[2]) + float(row[4])]]
                except KeyError:
                    #ignore anything not listed in names.json
                    pass

    print('loading powertrace')
    fmt = PWL_format(args.time_prefix, args.time_precision, args.amplitude_precision)
    with open(args.powertrace, newline='') as f:
        d = csv.DictReader(f)
        powertrace = get_PWLs(d, fmt, args.cycle_time, args.rise_time, args.fall_time, args.current_scale_factor)

    print('loading SPICE file')
    with open(args.spice) as f:
        spice = [l.split() for l in f.readlines()]

    print('getting bounding box from SPICE file')
    box = position_range(spice)

    if args.verbose:
        pprint(box)

    print('scaling floorplan')
    scale_floorplan(floorplan, box)

    if args.verbose:
        pprint(floorplan)

    print('converting to PWL')
    inductors = translate_to_PWL(floorplan, powertrace, spice, args.nearest_inductors)

    print('writing out inductors')
    with open(args.inductors, 'w') as f:
        json.dump(inductors, f, sort_keys=True, indent=4, separators=(',', ': '))

    print('writing out new SPICE file')
    with open(args.out, 'w') as f:
        for line in spice:
            for word in line:
                f.write(word)
                f.write(' ')
            f.write('\n')

