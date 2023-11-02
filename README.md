# code_explaination_tool
A python tool to help users learn programming and debug their code

The program begins by receiving user input to determine whether code is provided from the terminal or a local file. It then partitions the code into manageable chunks, loads them into a table in the EvaDB database, and generates a summary of the code. User questions about the code are processed using OpenAI’s LLM, ChatGPT, and responses are displayed. 

##Steps to read code read from terminal:
<img width="624" alt="Screenshot 2023-11-02 at 5 31 05 PM" src="https://github.com/fikremen/code_explaination_tool/assets/70618860/ea5fbf29-4d26-4577-bc9b-a794f7f752d7">

##Steps to read code read from file:
<img width="616" alt="Screenshot 2023-11-02 at 5 32 33 PM" src="https://github.com/fikremen/code_explaination_tool/assets/70618860/48143f26-ba06-45bb-89fd-2cd2d26f362d">
