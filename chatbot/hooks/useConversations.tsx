import { useState, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
export interface Message {
    id: string;
    role: 'human' | 'ai' | 'tool';
    content: string;
    tool_messages?:{ tool_name: string; content: string; status: string;}[]
}

export interface Conversation {
    id: string;
    title: string;
    updated_at?: string;
    messages: Message[]
}
const user_id = 'test_user_id'
export function useConversations() {
    const [conversations, setConversations] = useState<Conversation[]>([
        {
            id: uuidv4(),
            title: "New Chat",
            messages: []
        }
    ]);
    const [activeConversationId, setActiveConversationId] = useState<string>(conversations[0].id);


    const [isConvLoaded, setIsConvLoaded] = useState<boolean>(false);
    const [isMessagesLoaded, setIsMessagesLoaded] = useState<boolean>(false);
    useEffect(() => {
        async function fetchConversations() {
            try {
                
                const response = await fetch(`http://localhost:8000/conversations?user_id=${user_id}`)
                if (!response.ok) {
                    throw new Error(`HTTP error! status:${response.status}`)
                }

                const data = await response.json()
                
                
                if (data && data.length > 0) {
                    setConversations(prev => {
                        const existingIds = new Set(prev.map(c => c.id));

                        const newConversations = data
                            .filter((c: any) => !existingIds.has(c.id))
                            .map((c: any) => ({
                                ...c,
                                messages: []
                            }));

                        return [...prev, ...newConversations];
                    });
                }
                setIsConvLoaded(true);
            } catch (err) {
                console.error("Error while fetching", err);
                setIsConvLoaded(false);
            }
        }
        fetchConversations()
        // return () => fetchConversations()
    }, [])

    useEffect(() => {
        async function fetchMessages() {
            try {
                

                const response = await fetch(`http://localhost:8000/messages?conversation_id=${activeConversationId}&user_id=${user_id}`)
                if (!response.ok) {
                    throw new Error(`HTPP error! status: ${response.status}`)
                }
                const data = await response.json()
                if (data && data.length > 0) {
                    setConversations((currentConversations) =>
                        currentConversations.map(conversation => {
                            if (conversation.id !== activeConversationId) {
                                return conversation
                            }
                            return {
                                ...conversation,
                                messages: (data).map((msg:any) => ({
                                    id: msg.id,
                                    role: msg.role,
                                    content: msg.content
                                }))
                            }
                        })
                    )
                }
                setIsMessagesLoaded(true);
            } catch (err) {
                console.error("Error while fetching messages", err);
                setIsMessagesLoaded(false);
            }
        }
        if (activeConversationId)
            fetchMessages()
        // return () => fetchMessages();
    }, [activeConversationId])

    return { activeConversationId, setActiveConversationId, conversations, setConversations, isConvLoaded, isMessagesLoaded }
}