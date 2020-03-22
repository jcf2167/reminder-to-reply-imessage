import sqlite3
import datetime
import subprocess
import pandas as pd
import os

"""
$ say -v '?'

Alex                en_US    # Most people recognize me by my voice.
Daniel              en_GB    # Hello, my name is Daniel. I am a British-English voice.
Fred                en_US    # I sure like being inside this fancy computer
Karen               en_AU    # Hello, my name is Karen. I am an Australian-English voice.
Victoria            en_US    # Isn't it nice to have a computer that will talk to you?
Tessa               en_ZA    # Hello, my name is Tessa. I am a South African-English voice.
"""
VOICE = 'Alex'

def print_formatted_message(title, body, width=90):
    box_line = lambda text: "*  " + text + (" " * (width - 6 - len(text))) + "  *"

    print(
    f"""
        {"*" * width}
        {box_line(title.strip())}
        {"*" * width}
        {box_line(body.expandtabs())}
        {box_line("")}
        {"*" * width}
    """)


def get_messages_df(conn):
    messages = pd.read_sql_query(
        """
        SELECT *, 
        datetime(date/1000000000 + strftime("%s", "2001-01-01") ,"unixepoch","localtime")  
        AS date_utc 
        FROM message
        """, 
        conn
    ) 

    messages['message_date'] = messages['date']
    messages['timestamp'] = messages['date_utc'].apply(lambda x: pd.Timestamp(x))
    messages['date'] = messages['timestamp'].apply(lambda x: x.date())
    messages['month'] = messages['timestamp'].apply(lambda x: int(x.month))
    messages['year'] = messages['timestamp'].apply(lambda x: int(x.year))

    messages.rename(
        columns={
            'ROWID' : 'message_id'
        }, 
        inplace = True
    )

    return messages


def get_handles_df(conn):
    handles = pd.read_sql_query("select * from handle", conn)
    handles.rename(
        columns={
            'id' : 'phone_number', 
            'ROWID': 'handle_id'
        }, 
        inplace = True
    )

    return handles


def fix_hidden_imessage_db():
    out = subprocess.check_output(
        'defaults write com.apple.finder AppleShowAllFiles YES', 
        shell=True
    )


def get_or_document_sender(row):
    contacts = get_all_contact_names()
    sender = contacts.get(row['phone_number'], row['phone_number'])

    if row['phone_number'] not in contacts:
        sender = input(f"Who is [{row['phone_number']}]? Last message=[{row['text']}]")

        with open('contacts', 'a') as f:
            f.write(f"{row['phone_number']},{sender}\n")

    return sender.strip()


def get_all_contact_names():
    contacts = {}
    with open('contacts', 'r') as f:
        for line in f.readlines():
            number, name = line.split(",")
            contacts[number] = name

    return contacts


def reply_to_message(phone_number):
    msg = input("Type your message: ")
    if msg and '[' not in msg:
        print("?")
        print(f"osascript sendMessage.applescript {phone_number} {msg}")
        out = subprocess.check_output(
            f"osascript sendMessage.applescript {phone_number} \"{msg}\"", 
            shell=True
        )
        print(out)
    else:
        print("Did not type a message...skipping reply.")


def main():
    fix_hidden_imessage_db()
    conn = sqlite3.connect(os.path.expanduser('~/Library/Messages/chat.db'))

    messages = get_messages_df(conn)    
    handles = get_handles_df(conn)

    chat_message_joins = pd.read_sql_query("select * from chat_message_join", conn)

    merged_messages_with_handles = pd.merge(
        messages[[
            'text', 
            'handle_id', 
            'date',
            'message_date' ,
            'timestamp', 
            'month',
            'year',
            'is_sent', 
            'message_id'
        ]],  
        handles[['handle_id', 'phone_number']], 
        on='handle_id', 
        how='left'
    )

    df_messages = pd.merge(
        merged_messages_with_handles, 
        chat_message_joins[['chat_id', 'message_id']], 
        on='message_id', 
        how='left'
    )

    df_last_msg_per_chat = df_messages.sort_values('message_date').groupby('chat_id').tail(1)
    print("Please respond to the following messages!")

    for index, row in df_last_msg_per_chat.iterrows(): 
        sender = get_or_document_sender(row)

        if row['is_sent'] == 1:
            if '?' in row['text']:
                print_formatted_message(
                    title=f"Seems like you asked a question to {sender}! You should poke them!", 
                    body=row['text'], 
                    width=100
                )
                print("Poke?")
                reply_to_message(row['phone_number'])

            continue

        if len(row['text'].split()) <= 2:  
            continue

        #subprocess.check_output(f"say -v {VOICE} \"You have messages from {sender}.\"", shell=True)
        print_formatted_message(sender, row['text'])  
        reply_to_message(row['phone_number'])  
        

if __name__ == "__main__":
    main()
