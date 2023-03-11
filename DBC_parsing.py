"""
Parse DBC file and generate random signal for one hour,
export generated signal to csv / mdf / binary file
"""

import cantools
from asammdf import MDF, Signal
import numpy as np

import random
import csv


# calculate sine value
def sin_signal(time, frequency, phase):
    pi = np.pi
    amplitude = 0.5
    sine_value = amplitude * np.sin(2 * pi * frequency * time + phase) + 0.5
    return sine_value


# transfer decimal value to binary value
def decimal_to_binary(self, num, length, order):
    # when the num < 0
    def intToBin(i, length):
        return (bin(((1 << length) - 1) & i)[2:]).zfill(length)

    if num < 0:
        dec_to_bin = intToBin(num, length)
    else:
        # delete suffix 0b
        dec_to_bin = bin(num).replace("0b", "")
        # insert 0 to no signal place
        if not len(dec_to_bin) > length:
            for i in range(length - len(dec_to_bin)):
                dec_to_bin = "0" + dec_to_bin
    if not order == "little_endian":  # if the signal MSB
        dec_to_bin = dec_to_bin[::-1]
    return dec_to_bin


class DBC_parser:
    def __init__(self):
        self.mdf = MDF()
        # random noise
        self.noise = np.random.normal(0, 1, 3600)

    # generate sine_data for csv and bin file output
    def generate_sine_data(self, dbc_data):
        sig_num = 0
        # get number of signals in DBC file
        for message in dbc_data.messages:
            msg_name = message.name
            msg_group = dbc_data.get_message_by_name(msg_name)
            for signal in msg_group.signals:
                sig_num = sig_num + 1

        # generate random value for each signal
        list_msg = []
        for i in range(sig_num):
            frequency = random.randint(1, 1000) / 10
            phase = random.randint(0, 20) / 10 * (np.pi)
            signal_list = []
            for second in range(3600):
                data = sin_signal(second / 100, frequency, phase)
                signal_list.append(data)
            list_msg.append(signal_list)
        return list_msg

    # write data to csv file
    def export_csv(self, data):
        header = data[0].keys()
        rows = [x.values() for x in data]
        with open("output.csv", "w", newline="") as fp:
            writer = csv.writer(fp, delimiter=",")
            writer.writerow(header)
            for row in rows:
                writer.writerow(row)

    # mapping signal list to bytearray
    def process_sig(self, sig_list, msg_length):
        # if the length of signal smaller than the DLC
        for i in range(msg_length * 8 - len("".join(sig_list))):
            sig_list.insert(0, "0")
        # transfer sig to bytearray
        signal = "".join(sig_list)
        b = [signal[i : i + 8] for i in range(0, len(signal), 8)]  # pack 8 bit per byte
        b.reverse()
        signal = "".join(b)
        process_signal = " ".join(
            [signal[i : i + 8] for i in range(0, len(signal), 8)]
        )  # insert " " per 8 bit
        # process_signal = process_signal + ' '
        encoded_string = process_signal.encode()
        byte_array = bytearray(encoded_string)
        return byte_array

    # map value in to predefined range
    # min<num<max, num<length, unsigned_num>=0
    def map_num_to_range(
        self, num, max, min, float, bit_length, signed, offset, factor
    ):
        if num < 0 and signed == False:
            num = (min - offset) / factor
        if num > max:
            num = num - (num - max)
        elif num < min:
            num = num + (min - num)
        if float:  # float signal or not?
            num = num
        else:
            num = int(num)
        while num.bit_length() > bit_length:
            num = num - 1
        return num

    # get dbc Message structure
    def readMsg(self, dbc_data, msg):
        Msg_structure = {
            "name": msg.name,
            "id": msg.frame_id,
            "length": msg.length,
            "sender": msg.senders,
            "group": dbc_data.get_message_by_name(msg.name),
            "sig_list": [],  # signal group in this msg
        }
        return Msg_structure

    # get dbc Signal structure
    def readSig(dbc_signal):
        Sig_structure = {
            "name": dbc_signal.name,
            "start": dbc_signal.start,
            "length": dbc_signal.length,
            "order": dbc_signal.byte_order,
            "is_signed": dbc_signal.is_signed,
            "min": dbc_signal.minimum,
            "max": dbc_signal.maximum,
            "offset": dbc_signal.offset,
            "factor": dbc_signal.scale,
            "unit": dbc_signal.unit,
            "is_float": dbc_signal.is_float,
            "receiver": dbc_signal.receivers,
        }
        return Sig_structure

    # according to dbc file, generate signal and export to csv file
    def generate_data_to_csv(self, dbc_file_name):
        output = []  # output of generated signal
        # load file
        db = cantools.database.load_file(dbc_file_name)
        # generate sinus distributed number
        gen_num = self.generate_sine_data(db)
        timestamps = 0

        # generate signal of one hour
        for i in range(3600):
            sig_num = 0  # number of needed signal
            for msg in db.messages:
                # read msg info
                Msg = self.readMsg(db, msg)
                for signal in Msg["group"].signals:
                    # read sig info
                    Sig = self.readSig(signal)

                    # if sig_length smaller than the start_bit, insert 0
                    for a in range(Sig["start"] - len("".join(Msg["sig_list"]))):
                        Msg["sig_list"].insert(0, "0")

                    # generate signal (physical value)
                    gen_sig = (
                        (Sig["max"] - Sig["min"]) * gen_num[sig_num][i]
                        + Sig["min"]
                        + self.noise[i] * (Sig["max"] - Sig["min"]) * 0.01
                    )
                    # transfer to raw_value (physical_value = raw_value * factor + offset)
                    gen_sig = (gen_sig - Sig["offset"]) / Sig["factor"]
                    # map sig in range
                    gen_sig = self.map_num_to_range(
                        gen_sig,
                        Sig["max"],
                        Sig["min"],
                        Sig["is_float"],
                        Sig["length"],
                        Sig["is_signed"],
                        Sig["offset"],
                        Sig["factor"],
                    )
                    # mapping to binary sig
                    bin_sig = decimal_to_binary(gen_sig, Sig["length"], Sig["order"])
                    Msg["sig_list"].insert(0, bin_sig)
                    sig_num = sig_num + 1

                byte_array = self.process_sig(Msg["sig_list"], Msg["length"])
                output_dict = {
                    "timestamps": timestamps,
                    "msg_name": Msg["name"],
                    "msg_id": Msg["id"],
                    "msg_length": Msg["length"],
                    "sender": Msg["sender"],
                    "signal": byte_array,
                }
                timestamps = timestamps + 0.01
                output.append(output_dict)
        self.export_csv(output)

    def generate_data_to_mf4(self, dbc_file_name):
        db = cantools.database.load_file(dbc_file_name)  # load file
        for msg in db.messages:
            # read msg info
            Msg = self.readMsg(db, msg)
            sigs = []  # list of signals in Msg

            for signal in Msg["group"].signals:
                # read sig info
                Sig = self.readSig(signal)

                mdf_time_list = np.array([])  # timestamps output for mdf file
                mdf_sig_list = np.array([])  # signal data output for mdf file
                timestamps = 0
                frequency = random.randint(1, 1000) / 10
                phase = random.randint(0, 20) / 10 * (np.pi)

                # generate signal for one hour
                for i in range(3600):
                    gen_num = sin_signal(timestamps, frequency, phase)
                    # generate signal (physical value)
                    gen_sig = (
                        (Sig["max"] - Sig["min"]) * gen_num
                        + Sig["min"]
                        + self.noise[i] * (Sig["max"] - Sig["min"]) * 0.01
                    )
                    # transfer to raw_value (physical_value = raw_value * factor + offset)
                    gen_sig = (gen_sig - Sig["offset"]) / Sig["factor"]
                    # if sig still in range
                    gen_sig = self.map_num_to_range(
                        gen_sig,
                        Sig["max"],
                        Sig["min"],
                        Sig["is_float"],
                        Sig["length"],
                        Sig["is_signed"],
                        Sig["offset"],
                        Sig["factor"],
                    )
                    mdf_sig_list = np.append(mdf_sig_list, gen_sig)
                    mdf_time_list = np.append(mdf_time_list, timestamps)
                    timestamps = timestamps + 0.01
                signal = Signal(
                    samples=mdf_sig_list,
                    timestamps=mdf_time_list,
                    name=Sig["name"],
                    unit=Sig["unit"],
                )
                sigs.append(signal)
            self.mdf.append(sigs, acq_name=Msg["name"])
        self.mdf.save("output.mf4")

    def generate_data_to_bin(self, dbc_file_name):
        f = open("output.bin", "wb")

        # load file
        db = cantools.database.load_file(dbc_file_name)
        # generate sinus distributed number
        gen_num = self.generate_sine_data(db)

        timestamps = 0

        for i in range(3600):  # begin loop
            sig_num = 0  # number of needed signal
            for msg in db.messages:
                Msg = self.readMsg(db, msg)  # read msg info
                # process header(ID, Dlc, Flags...)
                TimestampMicros = (int(timestamps * 1000000)).to_bytes(4, "little")
                MsgId = (Msg["id"]).to_bytes(4, "little")
                WhichCan = (0).to_bytes(1, "little")
                Dlc = (Msg["length"]).to_bytes(1, "little")
                Flags = (0).to_bytes(1, "little")
                RESERVED = (0).to_bytes(1, "little")
                signal_byte = (
                    TimestampMicros + MsgId + WhichCan + Dlc + Flags + RESERVED
                )

                for signal in Msg["group"].signals:
                    Sig = self.readSig(signal)  # read sig info
                    # generate signal (physical value)
                    gen_sig = (
                        (Sig["max"] - Sig["min"]) * gen_num[sig_num][i]
                        + Sig["min"]
                        + self.noise[i] * (Sig["max"] - Sig["min"]) * 0.01
                    )
                    # transfer to raw_value       (physical_value = raw_value * factor + offset)
                    gen_sig = (gen_sig - Sig["offset"]) / Sig["factor"]
                    # check if sig still in range
                    gen_sig = self.map_num_to_range(
                        gen_sig,
                        Sig["max"],
                        Sig["min"],
                        Sig["is_float"],
                        Sig["length"],
                        Sig["is_signed"],
                        Sig["offset"],
                        Sig["factor"],
                    )
                    # mapping to binary sig
                    if Sig["order"] == "little_endian":
                        bin_sig = (gen_sig).to_bytes(
                            (Sig["length"] + 7) // 8, "little", signed=Sig["is_signed"]
                        )
                    else:
                        bin_sig = (gen_sig).to_bytes(
                            (Sig["length"] + 7) // 8, "big", signed=Sig["is_signed"]
                        )

                    signal_byte = signal_byte + bin_sig
                    sig_num = sig_num + 1

                timestamps = timestamps + 0.01
                f.write(signal_byte)
        f.close()


if __name__ == "__main__":

    parser = DBC_parser()

    # parse DBC file
    file_name = "signal_data/test_encrypted.dbc"

    parser.generate_data_to_mf4(file_name)
    # parser.generate_data_to_csv(file_name)
    # parser.generate_data_to_bin(file_name)
