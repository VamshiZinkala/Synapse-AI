from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from typing import List
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), 'categories.json')
mcp = FastMCP(name="Expense Tracker")


@mcp.tool()
async def add_expense(user_id: str, date:str, amount:float, category:str, subcategory:str ="", note:str ="") -> dict:
    """Logs a new expense to the system. 
    
    Ensure you call 'get_allowed_categories' first to map the user's intent 
    to one of the accepted categories before executing this tool.
    """
    query = text("""
        INSERT into expenses (user_id, date, amount, category, subcategory, note)
        VALUES (:uid, :date, :amount, :category, :sub, :note)
        RETURNING id;
    """)
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(query, {
            "uid": user_id,
            "date": date,
            "amount": amount,
            "category": category,
            "sub": subcategory,
            "note": note
        })
        await db.commit()
        return {'status': 'success', 'id': result.scalar()}
    
@mcp.tool
async def list_expenses(user_id: str, start_date: str, end_date: str) -> List[dict]:
    '''List all expenses from the database'''
    query = text("""
        select id, date, amount, category, subcategory, note
        from expenses
        where user_id = :uid and date between :start and :end
        order by date asc;
    """)
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(query, {
            "uid": user_id,
            "start": start_date,
            "end": end_date
        })
        return list(result.mappings().all())

@mcp.tool()
async def summarize(user_id: str, start_date:str, end_date:str, category: str =None) -> List[dict]:
    '''Summarize expenses by category within an inclusive date range.'''
    base_query = text("""
        select category, sum(amount) as total_amount
        from expenses where user_id = :uid and date between :start and :end
    """)
    
    if category:
        base_query += "AND category = :cat"
    base_query += " group by category order by category asc;"

    async with AsyncSessionLocal() as db:
        result = await db.execute(text(base_query), {'uid': user_id, 'start': start_date, 'end': end_date, 'cat': category})
        return list(result.mappings().all())

# @mcp.resource("expense://categories", mime_type="application/json")
# def categories():
#     '''To get categories labels for expenses'''
#     with open(CATEGORIES_PATH, 'r', encoding='utf-8') as f:
#         return f.read()

@mcp.tool()
def get_allowed_categories() -> str:
    """Retrieves the list of valid expense categories allowed in the tracking system.
    
    Call this tool whenever a user wants to log an expense or ask about categories, 
    so you can accurately map their input to an official system label.
    """
    try:
        with open(CATEGORIES_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading categories: {str(e)}"
if __name__ == "__main__":
    mcp.run(transport="stdio")
