export default function MessageLoader() {
    return (
        <div className="space-y-6">
            <div className={`flex w-full justify-end`}>
                <div
                    className={`flex min-w-0 max-w-[88%] items-end gap-3 md:max-w-[70%] flex-row-reverse
                    }`}
                >
                    <div
                        className={`relative min-w-0 break-words rounded-[1.35rem] border px-5 py-3.5 text-sm leading-6 shadow-2xl backdrop-blur-xl md:text-[0.95rem]
                            rounded-br-md border-cyan-200/25 bg-cyan-300/15 text-cyan-50 shadow-cyan-950/20 space-y-5
                            `}
                    >
                        <div className="space-y-2">
                            <div className="animate-pulse rounded-md bg-cyan-200 h-4 w-[250px]"> </div>
                            <div className="animate-pulse rounded-md bg-cyan-200 h-4 w-[200px]"> </div>
                        </div>

                        <div className="space-y-2">
                            <div className="animate-pulse rounded-md bg-cyan-200 h-4 w-[250px]"> </div>
                        </div>

                    </div>
                </div>
            </div>
            <div className="flex-1 items-center space-y-7">

                <div className="space-y-7">
                    <div className="animate-pulse rounded-md bg-gray-500 h-4 w-[700px]"> </div>
                    <div className="animate-pulse rounded-md bg-gray-500 h-4 w-[500px]"> </div>
                    <div className="animate-pulse rounded-md bg-gray-500 h-4 w-[750px]"> </div>
                    <div className="animate-pulse rounded-md bg-gray-500 h-4 w-[400px]"> </div>
                    <div className="animate-pulse rounded-md bg-gray-500 h-4 w-[800px]"> </div>
                    <div className="animate-pulse rounded-md bg-gray-500 h-4 w-[400px]"> </div>
                    <div className="animate-pulse rounded-md bg-gray-500 h-4 w-[550px]"> </div>
                    <div className="animate-pulse rounded-md bg-gray-500 h-4 w-[300px]"> </div>
                </div>
            </div>
        </div>
    )
}