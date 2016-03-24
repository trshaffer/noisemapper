#!/usr/bin/env python

import json
import csv
import re
from pprint import pprint

CURRENT_SOURCE_PATTERN = re.compile('i', re.I)
PULSE_PATTERN = re.compile('pulse', re.I)
POSITION_PATTERN = re.compile('n', re.I)

def get_PWLs(powertrace, dt):
    '''
        Return a dictionary keyed by the columns powertrace. Each entry is a
        long string of the form PWL(t1 v1 t2 v2 ...) for the component.

        powertrace is a csv.DictReader
        dt is the cycle time, measured in ns
    '''
    result = dict()
    peak_rise = 0.1 * dt
    peak_fall = 0.1 * dt
    i = 0
    components = powertrace.fieldnames
    for c in components:
        result[c] = ['PWL(']

    for row in powertrace:
        cycle_start = dt * i
        peak = cycle_start + peak_rise
        cycle_end = peak + peak_fall
        for c in components:
            peak_amplitude = float(row[c])
            if peak_amplitude != 0.0:
                result[c].append(' %fN 0 %fN %f %fN 0' % (
                    cycle_start, peak, peak_amplitude, cycle_end))
        i = i + 1

    for c in components:
        if len(result[c]) > 1:
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

def get_i_position(e):
    '''
    If e is a current source, return the parsed position
    e is a split line to check
    '''
    if e and CURRENT_SOURCE_PATTERN.match(e[0]):
        i = indexof_match(POSITION_PATTERN, e)
        if i:
            return [float(x) for x in e[i].split('_')[1:]]

def i_position_range(spice):
    '''
    For the split lines in spice, find the bounding box of the current sources
    '''
    positions = []
    for e in spice:
        p = get_i_position(e)
        if p:
            positions.append(p)
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    return [[min(xs), max(xs)], [min(ys), max(ys)]]

def replace_pulse(e, s):
    '''
    Given the split list e containing a SPICE element, replace the pulse
    (if it exists) with the given string s
    '''
    pulse_index = indexof_match(PULSE_PATTERN, e)
    if pulse_index:
        return e[:pulse_index] + [s]
    else:
        return e

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

def translate_to_PWL(floorplan, powertrace, spice):
    '''
    Given a scaled floorplan fp, powertrace pt, and spice file sp, convert current
    sources to PWL representation using the given power data
    '''
    hit = 0
    miss = 0
    for i in range(len(spice)):
        if len(spice[i]) < 1 or not CURRENT_SOURCE_PATTERN.match(spice[i][0]):
            continue
        pos = get_i_position(spice[i])
        if not pos:
            continue
        comp = find_component(floorplan, pos)
        if not comp:
            miss += 1
            continue
        hit += 1
        spice[i] = replace_pulse(spice[i], powertrace[comp])
    print('\thit: %d\n\tmiss: %d' % (hit, miss))

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='The name mappings should be a JSON object of the form {"floorplan_name": "powertrace_name"}')
    parser.add_argument('-n', '--name-mappings', required=True, help='in JSON')
    parser.add_argument('-f', '--floorplan', required=True)
    parser.add_argument('-s', '--spice', required=True)
    parser.add_argument('-c', '--clock-frequency', required=True, help='in GHz')
    parser.add_argument('-o', '--out', required=True)
    parser.add_argument('-p', '--powertrace', required=True)
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
                floorplan[name_mappings[row[0]]] = [
                    [float(row[3]), float(row[1]) + float(row[3])],
                    [float(row[4]), float(row[2]) + float(row[4])]]

    print('loading powertrace')
    with open(args.powertrace, newline='') as f:
        d = csv.DictReader(f)
        powertrace = get_PWLs(d, 1.0 / float(args.clock_frequency))

    print('loading SPICE file')
    with open(args.spice) as f:
        spice = [l.split() for l in f.readlines()]

    print('getting bounding box for current sources')
    box = i_position_range(spice)

    print('scaling floorplan')
    scale_floorplan(floorplan, box)

    print('converting to PWL')
    translate_to_PWL(floorplan, powertrace, spice)

    print('writing out new SPICE file')
    with open(args.out, 'w') as f:
        for line in spice:
            for word in line:
                f.write(word)
                f.write(' ')
            f.write('\n')

