import csv
from dateutil.parser import parse
# dive number	date	time	sample time (min)	sample depth (ft)	sample temperature (F)	sample pressure (psi)	sample heartrate

# "dive number","date","time","sample time (min)","sample depth (ft)","sample temperature (F)","sample pressure (psi)","sample heartrate"

with open("dive details.csv", 'r') as csv_file:
    # sometimes tab/space separated.
    reader = csv.DictReader(csv_file)
    for row in reader:
        dive = {}
        dive['dive_number'] = row['dive number']
        dive['datetime'] = parse(row['date'] + "-" + row['time'], )
        # dive[;]

        print dive
