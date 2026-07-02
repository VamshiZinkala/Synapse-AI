import io
import os
from PIL import Image
from fastapi import UploadFile, APIRouter, File, Form, HTTPException
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
import pymupdf
import pymupdf4llm
import docx
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Literal, Optional
import pandas as pd
from langchain_core.documents import Document
import base64
import json
import uuid
from langchain_groq import ChatGroq
from database import AsyncSessionLocal
from models import DocumentChunk
router = APIRouter()


embedding_model = OpenAIEmbeddings(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["BASE_URL"],
    model="qwen3-embedding-0.6b"
)


# vision_llm = ChatGroq(
#     model="meta-llama/llama-4-scout-17b-16e-instruct",
#     temperature=0,
#     max_tokens=None,
#     # reasoning_format="parsed",
#     timeout=None,
#     max_retries=2,
#     api_key=os.environ["groq_api_key"]
# )

vision_llm = ChatOpenAI(
    model="qwen-3.6-27b", #ministral-3-14b-instruct-2512",
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["IMAGE_BASE_URL"]
)

vision_prompt = ChatPromptTemplate.from_messages([

    ("human", [
        {
            "type": "text",
            "text": """
            Analyze this technical diagram or schematic carefully.

            You MUST follow these strict rules:
            - Use ONLY information that is directly visible or clearly inferable from the image.
            - DO NOT guess, assume, or invent details.
            - If something is unclear, ambiguous, or not visible, explicitly state "not specified" or "cannot be determined from the image".
            - Do NOT assign specific product models, protocols, voltages, or system types unless they are explicitly written in the image.
            - Distinguish clearly between:
              (a) Observed facts (visible in the image)
              (b) Reasonable inferences (state them as "likely" or "inferred", not certain)
              (c) Unknowns (explicitly mark them)

            CRITICAL DOMAIN RULES:
            1. For ER Diagrams(including Chen's Notation with floating attribute bubbles): 
                - Identify primary Entities (rectangles) as Nodes of type "entity".
               - Group all connected visual attribute bubbles (ovals like Ssn, Fname, Name) directly INSIDE that parental Entity's `attributes` list. Do NOT create separate independent nodes for individual attributes.
               - Detect primary keys by looking for underlined text inside the bubbles (e.g., Ssn, Number) and mark their `is_key` field as "PK".
               - Treat diamond relationship shapes (like WORKS_FOR, MANAGES) as Edges connecting the respective entity nodes, capturing the visible cardinality mapping (e.g., '1', 'N', 'M').
            2. For Circuit Schematics: Identify Components (ICs, Resistors, Pins), Nets, Power Rails, and Ground lines.

            Provide two outputs:

            1. DETAILED DESCRIPTION:
            - Describe all visible components, connections, labels, and structure.
            - Explain relationships between components.
            - Mention uncertainties explicitly where applicable.

            2. TOPOLOGY JSON:
            Return a structured JSON object wrapped in ```json ... ``` tags with:
            - "nodes": array of component names (use generic names if unclear, e.g., "Module A", "Connector X1")
            - "edges": array of objects with:
                - "source"
                - "target"
                - "relationship" (e.g., "connected via cable", "power supply line", "signal line")

            Additional constraints:
            - If component names are unreadable, use descriptive placeholders (e.g., "Left Module", "Right Terminal Block").
            - Do NOT fabricate relationships that are not visibly supported.
            - Keep relationships simple and grounded (e.g., "wired to", not "controls" unless explicit).

            Output MUST strictly follow this format:
            {format_instructions}
            """,
        },

        {
            "type": "image_url",
            "image_url": {"url": "{image_url}", "detail": "high"}
        }
    ]),

])


class Edge(BaseModel):
    source: str = Field(
        description="The starting component, pin, or entity table name")
    target: str = Field(
        description="The ending component, pin, or entity table name")
    relationship: str = Field(
        description="How they connect (e.g., 'wired via cable', 'foreign key relation', 'flows into', 'power line')")
    cardinality_or_type: Optional[str] = Field(
        default=None,
        description="For ERD: '1-to-many', 'many-to-many'. For Circuits: 'serial', 'parallel', 'bus', 'ground', 'net'."
    )

class Attribute(BaseModel):
    name:str = Field(description="The exact text name of the field/column/attribute field seen within the table entity box")
    data_type: Optional[str] = Field(default="varchar", description='Data type if visible, e.g., INT, VARCHAR')
    is_key: Literal["PK", "FK", "none"] = Field(default="none", description="Is it a Primary Key (PK), Foreign Key (FK), or standard attribute field ('none')?")
    
class Node(BaseModel):
    name: str = Field(
        description="The distinct Entity/Table name or Component label (e.g., 'Users', 'Resistor R1', '-X101') seen in the image"
    )
    type: Literal["entity", "attribute", "component", "pin", "power_rail", "placeholder"] = Field(
        description="The structural paradigm classification category of this element node")
    metadata: Optional[dict] = Field(
        default={},
        description="Extra descriptive context. E.g., {'value_of_component': '10k ohm'} or {'wire_label': '-X101'}"
    )
    attributes: Optional[List[Attribute]] = Field(default=[], description="For ER Diagrams: A list of all attributes/columns belonging inside this table entity box. For Circuits: Leave as an empty list []")
    source: Literal["visible_text", "placeholder"] = Field(
        description="Whether the name came from visible text labels or a placeholder descriptive assignment"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level of identification"
    )


class ImageTopology(BaseModel):
    detailed_description: str = Field(
        description="A thorough text explanation of what this system is, the components visible, and the overarching conceptual flow."
    )
    nodes: List[Node] = Field(
        description="Array of Entity tables or Circuit components identified in the technical drawing image.")
    edges: List[Edge] = Field(
        description="n array of explicit line connections, data paths, or structural dependencies between nodes.")


vlm_parser = PydanticOutputParser(pydantic_object=ImageTopology)


async def generate_embedding(texts: list[str]) -> list[list[float]]:
    return await embedding_model.aembed_documents(texts)


def parse_text(file_bytes: bytes) -> list[Document]:
    return file_bytes.decode("utf-8", errors="ignore")


async def parse_pdf_to_langchain_docs(file_bytes: bytes, filename: str, thread_id: str) -> str:

    # Open the PDF directly from byte stream in memory
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")

    # since page chunk is True it will retrieve list of dictionaries (one for each page)
    page_dicts = pymupdf4llm.to_markdown(doc, page_chunks=True)

    final_documents = []
    text_splitter = MarkdownTextSplitter(chunk_size=500, chunk_overlap=50)
    chain = vision_prompt.partial(
        format_instructions=vlm_parser.get_format_instructions()) | vision_llm | vlm_parser

    for index, chunk in enumerate(page_dicts):
        # texts data storing
        page_text = chunk['text']
        page_number = chunk['metadata'].get('page_number')

        if page_text.strip():
            text_docs = text_splitter.create_documents(
                [page_text],
                metadatas=[
                    {'source': filename, 'thread_id': thread_id, 'page_number': page_number}]
            )
            final_documents.extend(text_docs)

        # image data
        page = doc[index]
        image_list = page.get_images(full=True)

        if image_list:
            print(f"Found images: {len(image_list)} on page{page_number}")

            for img_meta in image_list:
                xref = img_meta[0]  # reference object
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                ext = base_image['ext']

                img_b64 = base64.b64encode(img_bytes).decode('utf-8')

                try:
                    vlm_response = await chain.ainvoke({
                        "image_url": f"data:image/{ext};base64,{img_b64}"
                    })

                    nodes_list = []
                    for n in vlm_response.nodes:
                        meta_str = json.dumps(n.metadata) if n.metadata else "{}"
                        
                        attr_strings = []
                        if n.attributes:
                            for attr in n.attributes:
                                key_tag = f" [{attr.is_key}]" if attr.is_key != "none" else ""
                                d_type = f" ({attr.data_type})" if attr.data_type and attr.data_type != "not specified" else ""
                                attr_strings.append(f"    * Attribute: {attr.name}{key_tag}{d_type}")
                        
                        attr_block = "\n" + "\n".join(attr_strings) if attr_strings else " (None)" # attributes concat
                        
                        nodes_list.append(
                            f"- **{n.name}** [Type: {n.type}, Source: {n.source}, Confidence: {n.confidence}], Metadata: {meta_str}"
                            f" Attributes/Fields:{attr_block}"
                        )
                    nodes_str = "\n".join(nodes_list)

                    edges_list = []
                    for e in vlm_response.edges:
                        c_type = f" | Type: {e.cardinality_or_type}" if e.cardinality_or_type else ""
                        edges_list.append(
                            f"- {e.source} ===({e.relationship}{c_type})===> {e.target}")
                    edges_str = "\n".join(edges_list)

                    topology_text = f"""[FILE_TYPE: IMAGE_TOPOLOGY]
IMAGE_SOURCE: Embedded in {filename}
EMBEDDED_PAGE: {page_number}

STRUCTURED_GRAPH_DATA:
Nodes (Components): {nodes_str}
Edges (Connections): {edges_str}

DETAILED_DESCRIPTION:
{vlm_response.detailed_description}"""

                    img_doc = Document(
                        page_content=topology_text,
                        metadata={
                            'source': filename, 'thread_id': thread_id, 'page_number': page_number,
                            'raw_topology': {
                                "nodes": [n.model_dump() for n in vlm_response.nodes],
                                "edges": [e.model_dump() for e in vlm_response.edges]
                            }
                        }
                    )

                    final_documents.append(img_doc)
                except Exception as e:
                    print(
                        f"Failed to process embedded image on page{page_number}: {str(e)}")
                    continue

    return final_documents


def parse_docx(file_bytes: bytes) -> str:
    doc_stream = io.BytesIO(file_bytes)
    doc = docx.Document(doc_stream)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])


def parse_spreadsheet(file_bytes: bytes, file_type: str) -> str:
    doc_stream = io.BytesIO(file_bytes)
    if file_type == 'csv':
        df = pd.read_csv(doc_stream)
    else:
        df = pd.read_excel(doc_stream)

    row_strings = []
    for _, row in df.iterrows():
        # convert each row into a semantic narrative sentence
        items = [f"{col}:{val}" for col, val in row.items() if pd.notna(val)]
        row_strings.append("Data record: " + ", ".join(items))
    return "\n".join(row_strings)


@router.post('/uploadfile')
async def upload_file(file: UploadFile = File(...), thread_id: str = Form(...), user_id: str = Form(...)) -> dict:
    try:
        file_bytes = await file.read()
        filename = file.filename or "unknown"
        ext = filename.split(".")[-1].lower()

        # 1. parse document (load) and chunk
        if ext == 'pdf':
            langchain_documents = await parse_pdf_to_langchain_docs(
                file_bytes, filename, thread_id)  # parse and chunk done
        else:
            if ext in ["txt", "md"]:
                raw_text = parse_text(file_bytes)
            elif ext == 'docx':
                raw_text = parse_docx(file_bytes)
            elif ext in ["csv", "xlsx"]:
                raw_text = parse_spreadsheet(file_bytes)

            # split into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500, chunk_overlap=50)

            langchain_documents = text_splitter.create_documents(
                [raw_text],
                metadatas=[{'source': filename,
                            'thread_id': thread_id, 'page_number': None}]
            )

        if not langchain_documents:
            return {'status': 'error', 'messages': 'No text could be extracted.'}

        # 2. Batch embedding
        texts_to_embed = [doc.page_content for doc in langchain_documents]

        # sending them all to the embedding model at once
        vectors = await generate_embedding(texts_to_embed)

        async with AsyncSessionLocal() as db:
            db_chunks = []
            for doc, vector in zip(langchain_documents, vectors):
                db_chunks.append(DocumentChunk(
                    conversation_id=uuid.UUID(doc.metadata['thread_id']),
                    user_id=user_id,
                    content=doc.page_content,
                    embedding=vector,
                    source_file=doc.metadata['source'],
                    page_number=doc.metadata.get('page_number'),
                    raw_topology=doc.metadata.get('raw_topology')
                ))

            db.add_all(db_chunks)
            await db.commit()

        return {'status': 'success', 'chunks': len(langchain_documents)}
    except Exception as e:
        print(f" CRITICAL UPLOAD ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Failed to process document: {str(e)}")


@router.post('/uploadimage')
async def upload_image(file: UploadFile = File(...), thread_id: str = Form(...), user_id: str = Form(...)) -> dict:
    try:
        file_bytes = await file.read()
        filename = file.filename or "unknown_image.jpg"
        
        # img = Image.open(io.BytesIO(file_bytes))

        # buffer = io.BytesIO()
        # img.save(buffer, format="PNG")
        
        image_b64 = base64.b64encode(file_bytes).decode('utf-8')

        chain = vision_prompt.partial(
            format_instructions=vlm_parser.get_format_instructions()) | vision_llm | vlm_parser

        print("VLM invoking")

        vlm_response = await chain.ainvoke({
            "image_url": f"data:{file.content_type};base64,{image_b64}"
        })
        # print(vlm_response)
        nodes_list = []
        for n in vlm_response.nodes:
            meta_str = json.dumps(n.metadata) if n.metadata else "{}"
            
            attr_strings = []
            if n.attributes:
                for attr in n.attributes:
                    key_tag = f" [{attr.is_key}]" if attr.is_key != "none" else ""
                    d_type = f" ({attr.data_type})" if attr.data_type and attr.data_type != "not specified" else ""
                    attr_strings.append(f"    * Attribute: {attr.name}{key_tag}{d_type}")
            
            attr_block = "\n" + "\n".join(attr_strings) if attr_strings else " (None)" # attribute
            
            nodes_list.append(
                f"- **{n.name}** [Type: {n.type}, Source: {n.source}, Confidence: {n.confidence}], Metadata: {meta_str}"
                f" Attributes/Fields:{attr_block}"
            )
        nodes_str = "\n".join(nodes_list)

        edges_list = []
        for e in vlm_response.edges:
            c_type = f" | Type: {e.cardinality_or_type}" if e.cardinality_or_type else ""
            edges_list.append(
                f"- {e.source} ===({e.relationship}{c_type})===> {e.target}")
        edges_str = "\n".join(edges_list)

        topology_text = f"""
        [FILE_TYPE: IMAGE_TOPOLOGY]
        IMAGE_NAME: {filename}

        STRUCTURED_GRAPH_DATA:
        Nodes (Components): {nodes_str}
        Edges (Connections): {edges_str}

        DETAILED_DESCRIPTION:
        {vlm_response.detailed_description}
        """
        print("embedding started")
        vector = await generate_embedding([topology_text])

        async with AsyncSessionLocal() as db:
            new_chunk = DocumentChunk(
                conversation_id=uuid.UUID(thread_id),
                user_id=user_id,
                content=topology_text,
                embedding=vector[0],
                source_file=filename,
                page_number=None,
                raw_topology={
                    "nodes": [n.model_dump() for n in vlm_response.nodes],
                    "edges": [e.model_dump() for e in vlm_response.edges]
                }
            )
            db.add(new_chunk)
            await db.commit()

        print("Image info successfully indexed")

        return {'status': 'success', 'message': 'Image processed and indexed successfully'}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Failed to process image: {str(e)}")
