import React, { memo } from "react";
import ReactMarkdown from "react-markdown";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import MessageComponent from "./MessageComponent";
import AILoader from "./AILoader";
import dynamic from 'next/dynamic';
import CodeLoader from "./CodeLoader";
import remarkGfm from "remark-gfm";
import MessageLoader from "./MessageLoader";
import ToolComponent from "./ToolComponent";


const SyntaxHighlighter = dynamic(
    async () => {
        const mod = await import('react-syntax-highlighter');
        return mod.Prism;
    },

    {
        ssr: false,
        loading: () => (
            <CodeLoader />
        ),
    }

)

const markdownComponents = {
    code({ node, inline, className, children, ...props }: any) {
        const match = /language-(\w+)/.exec(className || '')
        if (!inline && match) {
            return (
                <SyntaxHighlighter
                    style={vscDarkPlus as any}
                    language={match[1]}
                    PreTag="div"
                    className="rounded-md my-4! text-sm max-w-full! overflow-x-auto"
                    {...props}
                >
                    {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
            )
        }
        return (
            <code className="rounded-md bg-white/10 px-1.5 py-0.5 text-cyan-200 break-words whitespace-pre-wrap [overflow-wrap:anywhere]"
                {...props}
            >
                {children}
            </code>
        )
    }
}
const ChatMessages = memo(function ChatMessages({ messages, isMessagesLoaded }: any) {
    return (
        <>
            {messages.map((msg: any) => {
                if (msg.role === 'ai') {
                    //     if (!msg.content) {
                    //         return <AILoader key={msg.id} />
                    //     }


                    //     return (
                    //         <div key={msg.id} className="prose prose-invert w-full min-w-0 max-w-full break-words">
                    //             <ReactMarkdown
                    //                 remarkPlugins={[remarkGfm]}
                    //                 key={msg.content.length}
                    //                 components={markdownComponents}
                    //             >
                    //                 {msg.content}
                    //             </ReactMarkdown>
                    //         </div>
                    //     )
                    // }

                    // // Human message component style
                    // return (<MessageComponent
                    //     key={msg.id}
                    //     data={msg.content}
                    //     isHuman={true}
                    // />)

                    return (
                        <div key={msg.id}>
                            {msg.tool_messages?.map((tool: any) => (
                                <ToolComponent
                                    key={tool.tool_id}
                                    tool_name={tool.tool_name}
                                    content={tool.content}
                                    status={tool.status}
                                />
                            ))}

                            {!msg.content && !(msg.tool_messages && msg.tool_messages.length > 0) ? (
                                <AILoader />
                            ) : (
                                <div className="prose prose-invert w-full min-w-0 max-w-full break-words">
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        key={msg.content.length}
                                        components={markdownComponents}
                                    >
                                        {msg.content}
                                    </ReactMarkdown>
                                </div>
                            )}
                        </div>
                    )

                }

                return (
                    <MessageComponent
                        key={msg.id}
                        data={msg.content}
                        isHuman={true}
                    />
                );

            })}
        </>
    );
});

export default ChatMessages;