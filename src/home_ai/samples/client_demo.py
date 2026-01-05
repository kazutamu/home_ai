import asyncio
from temporalio.client import Client
from .agent_workflow import ChatAgentWorkflow

TASK_QUEUE = "agent-q"
WF_ID = "chat-session-1"


async def main():
    client = await Client.connect("localhost:7233")

    # 1セッション=1Workflow を開始（すでに動いてたら無視してOK）
    try:
        await client.start_workflow(
            ChatAgentWorkflow.run,
            id=WF_ID,
            task_queue=TASK_QUEUE,
        )
        print("Workflow started:", WF_ID)
    except Exception:
        print("Workflow already running:", WF_ID)

    handle = client.get_workflow_handle(WF_ID)

    # 1回目入力
    await handle.signal(ChatAgentWorkflow.new_input, "最初の入力です")
    print("Sent input v1")

    # 少し待って、処理途中で2回目入力（割り込み）
    await asyncio.sleep(2)
    await handle.signal(ChatAgentWorkflow.new_input, "割り込み入力です（これを優先）")
    print("Sent input v2 (interrupt)")

    # 状態をポーリングして、完了したreplyを表示
    while True:
        st = await handle.query(ChatAgentWorkflow.status)
        print("status:", st)
        if st.last_done_version == st.input_version and st.last_reply:
            print("DONE reply:", st.last_reply)
            break
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
