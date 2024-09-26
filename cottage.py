import os
from typing import Any, Dict, List, Tuple

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import AsyncClient
from tavily import TavilyClient

load_dotenv()


async def get_openai_response(query: str) -> Any:
    print(f"> Query: {query}/n")
    client = AsyncClient(
        api_key=os.getenv("OPENAI_API_KEY")
    )  # Replace with your actual API key
    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",  # Replace with the desired model
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": query},
        ],
    )

    final_response = response.choices[0].message.content
    print(f"> Result: {final_response}")
    return final_response


async def parse_cottage_nodes(xml_data: str) -> list:
    """
    Parses the given XML data and extracts all nodes whose tags start with 'COTTAGE_'.

    Args:
        xml_data (str): The XML data as a string.

    Returns:
        list: A list of BeautifulSoup Tag objects whose tags start with 'COTTAGE_'.
    """
    soup = BeautifulSoup(xml_data, "xml")
    cottage_nodes = [
        (tag.name, tag.get_text())
        for tag in soup.find_all(lambda tag: tag.name.startswith("COTTAGE_"))
    ]
    return cottage_nodes


tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


async def query_tavily_api(data: Dict[str, str]) -> Dict[str, Any]:
    """
    Queries the Tavily API for each key-value pair in the provided dictionary.

    Args:
        data (Dict[str, str]): A dictionary where each key-value pair represents a query parameter.

    Returns:
        Dict[str, Any]: A dictionary with the same keys, where each value is the response from the Tavily API.
    """
    results = {}
    for key, value in data.items():
        response = await tavily_client.search(value)["results"]
        results[key] = response
    return results


def data_enrichment(nodes: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    return [
        (
            query_tag.replace("<COTTAGE_", "<"),
            tavily_client.search(tag_contents)["results"],
        )
        for query_tag, tag_contents in nodes
    ]


class Cottage:
    def __init__(self, token_vocab: Dict[str, str] = {}):
        self.recursion_loop_limit = 5
        self.current_iteration_count = 0
        self.token_vocab = {f"<COTTAGE_{key}": value for key,value in token_vocab.items()}
        self.cot_prompt = """
            The question given by the user is:
            ```
            {query}
            ```.

            The data given is: 
            ```
            {data}
            ```

            Please answer the question.
            """
        self.requirements_prompt = """Analyze the current question, and tell me the requirements of the type of information. Generate a structured XML for the information required by creating tags using the vocabulary provided to you. 
        
        The vocabulary that you know for generating XML is:
        ```
        {vocab}
        ```

        The user query is:
        ```
        {query}
        ```
        """
        self.current_result: str | None = None

    async def __call__(self, query: str) -> Any:
        while (self.current_result is None or "<COTTAGE_" in self.current_result) and self.current_iteration_count < self.recursion_loop_limit:
            if os.getenv("ENV", "debug").lower() == "debug":
                print(f"Pass {self.current_iteration_count+1}, Step 1: Requirement analysis")
            evaluation_prompt_results = await get_openai_response(self.requirements_prompt.format(vocab=self.token_vocab, query=query))
            parsed_cottage_nodes = await parse_cottage_nodes(
                evaluation_prompt_results[
                    evaluation_prompt_results.index(
                        "<"
                    ) : evaluation_prompt_results.rindex(">")
                ]
            )
            data_enriched_results = data_enrichment(parsed_cottage_nodes)

            self.current_result = await get_openai_response(self.cot_prompt.format(data=data_enriched_results, query=query))

        self.current_iteration_count = 0
        return self.current_result
    
cottage_ob = Cottage(token_vocab={
    "TRANSIENT": "Temporary data that needs to lookup for evolving data. Associated with words like 'current', 'last', 'previous', or other relative phrases that change over time. Example: The current President of the United States is Joe Biden, the previous president was Donald Trump",
    "NON_TRANSIENT": "Data that does not change over time. For example: India got independence in 15th August, 1947"
})

import asyncio

print(asyncio.run(cottage_ob("How many goals has Lionel Messi scored till now?")))
