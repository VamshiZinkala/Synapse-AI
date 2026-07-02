export async function POST(req) {
    const { message, thread_id } = await req.json();
    const fastApiResponse = await fetch('http://localhost:8000/chat', {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({"message": message, "thread_id": thread_id}),
        cache: 'no-store'
    })
    
    return new Response(fastApiResponse.body, {
        headers: {
            "Content-Type": 'text/plain; charset=utf-8',
        },
    });
}