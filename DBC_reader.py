"""
read DBC data
"""

import cantools


class DBC_message:
    def __init__(self, file_name, message_name):
        self.file_name = file_name
        self.message_name = message_name

    def read_Msg(self):
        dbc_data = cantools.database.load_file(self.file_name)
        return dbc_data.messages

    def read_Sig(self):
        Message = cantools.database.load_file(self.file_name).get_message_by_name(
            self.message_name
        )
        return Message.signals


if __name__ == "__main__":

    file_name = "signal_data/test_encrypted.dbc"
    msg_name = "X_RT1O4b0NsYhaEJf34ztkNkOJbcXXhXf7"

    loadDbc = DBC_message(file_name, msg_name)

    Msg = loadDbc.read_Msg()
    Sigs = loadDbc.read_Sig()

    for Sig in Sigs:
        print(Sig)
