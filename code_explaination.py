import os
import shutil 
import pandas as pd
import evadb

os.environ['KMP_DUPLICATE_LIB_OK']='True' # added to get around a libiomp5.dylib initialization error

MAX_CHUNK_SIZE = 10000

# temporary file paths
CODE_CSV_PATH = os.path.join("evadb_data", "tmp", "code.csv")
SUMMARY_PATH = os.path.join("evadb_data", "tmp", "summary.csv")


def receive_input():
    """Receives user input."""
    print("This app summarizes code and lets you ask questions about the code to help you learn.\n")
    while(True):
        user_input = str(input(
            "Would you like for the code to be read from a local file or would you like to enter a single line of code in the terminal:? ('file', or 'terminal'): ")
        ).lower()

        if(user_input in ["terminal"]):
            user_input = {"from_terminal": True}
            # get code block
            code_block = str(input("🧑‍💻 Enter the code you would like summarized:"))
            user_input["code_block"] = code_block
            break
        elif (user_input in ["file"]): 
            user_input = {"from_terminal": False}
            code_block_local_path = str(input("🧑‍💻 Enter the local path of the file: "))
            user_input["code_block_local_path"] = code_block_local_path
            break
        else:
            print("❌ Invalid input. Please try again.")

    # get OpenAI key if needed
    try:
        api_key = os.environ["OPENAI_KEY"]
    except KeyError:
        api_key = str(input("🔑 Enter your OpenAI key: "))
        os.environ["OPENAI_KEY"] = api_key
    return user_input


def partition_code_string(raw_code_string: str):
    # Check if the raw code string is smaller than or equal to the maximum chunk size
    if len(raw_code_string) <= MAX_CHUNK_SIZE:
        return [{"text": raw_code_string}]

    # Calculate the number of chunks
    num_chunks = 2
    while (len(raw_code_string) / num_chunks) > MAX_CHUNK_SIZE:
        num_chunks += 1

    # Calculate chunk size
    chunk_size = len(raw_code_string) // num_chunks

    # Partition the raw code string
    partitioned_code_string = [{"text": raw_code_string[i:i + chunk_size]} for i in range(0, len(raw_code_string), chunk_size)]

    # Remove the last chunk if it's too small
    if (len(partitioned_code_string[-1]["text"])) < 30:
        partitioned_code_string.pop()

    return partitioned_code_string


def partition_summary(prev_summary: str):
    chunks = 2
    while (len(prev_summary) / chunks) > MAX_CHUNK_SIZE:
        chunks += 1
    chunk_size = int(len(prev_summary) / chunks)
    
    new_summary = [{"summary": prev_summary[i : i + chunk_size]} for i in range(0, len(prev_summary), chunk_size)]
    
    if len(new_summary[-1]["summary"]) < 30:
        new_summary.pop()
    
    return new_summary


def generate_summary(cursor: evadb.EvaDBCursor):
    code_list = cursor.table("Code").select("text").df()["code.text"]
    
    if len(code_list) == 1:
        summary = code_list[0]
    else:
        summary = detailed_summary(cursor)

    summary_to_csv(summary)
    load_summary_table(cursor)

def detailed_summary(cursor):
    generate_summary_res = cursor.table("Code").select("ChatGPT('summarize the code', text)")
    responses = generate_summary_res.df()["chatgpt.response"]
    
    summary = " ".join(responses)

    while len(summary) > MAX_CHUNK_SIZE:
        partitioned_summary = partition_summary(summary)
        summary_to_csv(partitioned_summary)
        load_summary_table(cursor)
        
        generate_summary_res = cursor.table("Summary").select("ChatGPT('summarize in detail', summary)")
        responses = generate_summary_res.df()["chatgpt.response"]
        summary = " ".join(responses)

    return summary

def summary_to_csv(summary):
    df = pd.DataFrame([{"summary": summary}])
    df.to_csv(SUMMARY_PATH)

def load_summary_table(cursor):
    cursor.drop_table("Summary", if_exists=True).execute()
    cursor.query("""CREATE TABLE IF NOT EXISTS Summary (summary TEXT(100));""").execute()#todo find out what the text 100 is
    cursor.load(SUMMARY_PATH, "Summary", "csv").execute()

def generate_response(cursor: evadb.EvaDBCursor, question: str) -> str:
    """Generates question response with llm."""

    code_blocks_count = len(cursor.table("Code").select("text").df()["code.text"])
    if code_blocks_count == 1:
        response = get_chatgpt_response(cursor, question, "Code", "text")
    else:
        # generate summary of the code if its too long
        if not os.path.exists(SUMMARY_PATH):
            generate_summary(cursor)

        response = get_chatgpt_response(cursor, question, "Summary", "summary")
    return response

def get_chatgpt_response(cursor: evadb.EvaDBCursor, question: str, table_name: str, column_name: str) -> str:
    response = (
        cursor.table(table_name)
        .select(f"ChatGPT('{question}', {column_name})")
        .df()["chatgpt.response"][0]
    )
    return response

def generate_local_file_string(code_path: str) -> str: 
    file_not_read = True
    while (file_not_read):
        try:
            with open(code_path, "r") as file:
                code = file.read()
        except FileNotFoundError:
            print(f"File not found at {code_path}")
            code = None

        # Check if the code was successfully read
        if code is not None:
            print("Code read successfully:")
            file_not_read = False
        else:
            print("Error reading code.")
    return code



def cleanup():
    """Removes any temporary file / directory created by EvaDB."""
    if os.path.exists("evadb_data"):
        shutil.rmtree("evadb_data")


if __name__ == "__main__":
    # receive input from user
    user_input = receive_input()

    try:
        # establish evadb api cursor
        cursor = evadb.connect().cursor()

        if user_input["from_terminal"]:
            #reading code from terminal
            code_string = user_input["code_block"]
        else:
            #reading code from file
            code_string = generate_local_file_string(user_input["code_block_local_path"])

       
        # Partition the code string
        if code_string is not None:
            partitioned_code_string = partition_code_string(code_string)

            dataframe = pd.DataFrame(partitioned_code_string)
            dataframe.to_csv(CODE_CSV_PATH)

        # load chunked code into table
        cursor.drop_table("Code", if_exists=True).execute()
        cursor.query("""CREATE TABLE IF NOT EXISTS Code (text TEXT(50));""").execute() #todo find out what the TEXT 50 is
        cursor.load(CODE_CSV_PATH, "Code", "csv").execute()
        print("\nHere is a summary of the code:\n")
        response = generate_response(cursor, "Can you summarize the code in less than 3 sentences?")
        print(response)
        print("--------------------------------------------------")

        print("Do you have any other questions about the code?")
        while True:
            question = str(input("Question (enter 'exit' to exit): "))
            if question.lower() == "exit":
                break
            else:
                # Generate response with chatgpt
                print("That's a good question! Generating response...")
                response = generate_response(cursor, question)
                print("--------------------------------------------------")
                print(response)

        cleanup()
        print("Session ended")

    except Exception as e:
        cleanup()
        print(f"!!!Session ended with an error!!! {e}")
