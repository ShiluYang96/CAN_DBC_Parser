"""
A simple tool to convert between vehicle diagnostic data in different file formats (csv, mdf, blf).
"""

from asammdf import MDF, Signal
import can
import csv
import re


def removesuffix(self, suffix):
    # suffix='' should not call self[:-0].
    if suffix and self.endswith(suffix):
        return self[:-len(suffix)]
    else:
        return self[:]


def mdf_to_csv_converter(filename):
    """one channel one file"""
    # open mdf file
    mdf = MDF(filename)
    # convert mdf file to csv file
    mdf.export(fmt='csv', filename=removesuffix(filename, ".mf4") + ".csv")


def mdf_to_blf_converter(filename):
    """lose CAN ID, channel..."""
    # open mdf file
    mdf = MDF(filename)
    # load pandas dataFrame
    a = mdf.iter_groups(raw=True)

    def to_msg(sig, indexs, channel):
        """Convert a LogLine tuple into a python-can Message"""
        return can.Message(timestamp=indexs,
                           arbitration_id=0,
                           is_remote_frame=0,
                           data=sig.loc[indexs].values[0:-1],
                           channel=channel)

    channel = 0
    # write to blf format
    with can.Logger(removesuffix(filename, ".mf4") + ".blf") as writer:
        for sig in a:
            for indexs in sig.index:
                writer.on_message_received(to_msg(sig, indexs, channel))
        channel = channel + 1


def blf_to_csv_converter(filename):
    log = can.BLFReader(filename)
    log = list(log)
    log_output = []

    for msg in log:
        msg = str(msg)
        a = re.split(
            'Timestamp:     |    ID: |                DLC: |     Channel: |    ',
            msg)
        log_output.append([a[1], a[2], a[3], a[4], a[5], a[6]])

    with open(removesuffix(filename, ".blf") + ".csv", "w", newline='') as f:
        writer = csv.writer(f,
                            delimiter=';',
                            quotechar='\"',
                            quoting=csv.QUOTE_ALL)
        writer.writerows(log_output)


def blf_to_mf4_converter(filename):
    """lose CAN ID, DLC, Channel..."""
    log = can.BLFReader(filename)
    log = list(log)
    data = []
    t = []
    mdf = MDF()
    for msg in log:
        msg = str(msg)
        a = re.split(
            'Timestamp:     |    ID: |                DLC: |     Channel: |    ',
            msg)
        data.append(a[5])
        t.append(a[1])

    s1 = Signal(samples=data, timestamps=t, name='None', raw=True)
    mdf.append(s1)
    mdf.save(removesuffix(filename, ".blf") + ".mf4")


if __name__ == "__main__":
    filename = 'output.mf4'

    mdf_to_csv_converter(filename)
    # mdf_to_blf_converter(filename)
    # blf_to_csv_converter(filename)
    # blf_to_mf4_converter(filename)
