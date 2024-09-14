from typing import Optional

import chainlit as cl
import httpx
from chainlit.input_widget import Slider, Select, Switch, TextInput, Tags
from openai import AsyncOpenAI

openai_models = [
    "o1-preview", "o1-mini",
    "gpt-4o-mini", "gpt-4o",
    "gpt-4", "gpt-4-turbo",
    "gpt-3.5-turbo",
]


async def create_client(base_url, api_key, http_proxy):
    client = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        http_client=httpx.AsyncClient(
            verify=False,
            proxies={"all://": http_proxy[0]},
        ) if http_proxy else None,
    )
    return client


async def get_model_list(client):
    res = await client.models.list()
    model_ids = []
    for model_list in res:
        if model_list[0] == 'data':
            models = model_list[1]
            model_ids += [model.id for model in models]
            break
    print(model_ids)
    return model_ids


async def create_settings(settings):
    chat_settings = cl.ChatSettings(
        [
            TextInput(
                id="base_url",
                label="OPENAI_BASE_URL",
                initial=settings.get("base_url"),
            ),
            TextInput(
                id="http_proxy",
                label="http_proxy",
                initial=settings.get("http_proxy"),
            ),
            TextInput(
                id="api_key",
                label="OPENAI_API_KEY",
                initial=settings.get("api_key"),
            ),
            Select(
                id="model",
                label="model",
                values=settings.get("models"),
                initial_index=0,
                tooltip="ID of the model to use. You can use the List models API to see all of your available models."
            ),
            Switch(
                id="stream",
                label="stream",
                initial=settings.get("stream"),
                tooltip=
                "Whether to stream back partial progress. If set, tokens will be sent as data-only "
                "server-sent events as they become available, with the stream terminated by a data: [DONE] message.",
            ),
            Slider(
                id="max_tokens",
                label="max_tokens",
                initial=settings.get("max_tokens"),
                min=64,
                max=131072,  # 128k
                step=1,
                tooltip=
                "The maximum number of tokens that can be generated in the completion.\n"
                "The token count of your prompt plus max_tokens cannot exceed the model's context length.",
            ),
            Slider(
                id="temperature",
                label="temperature",
                initial=settings.get("temperature"),
                min=0,
                max=1,
                step=0.01,
                tooltip=
                "What sampling temperature to use, between 0 and 2. Higher values like 0.8 will make the output more "
                "random, while lower values like 0.2 will make it more focused and deterministic.\n"
                "We generally recommend altering this or top_p but not both.",
            ),
            Slider(
                id="top_p",
                label="top_p",
                initial=settings.get("top_p"),
                min=0,
                max=1,
                step=0.01,
                tooltip=
                "An alternative to sampling with temperature, called nucleus sampling, where the model considers the "
                "results of the tokens with top_p probability mass. So 0.1 means only the tokens comprising the top "
                "10% probability mass are considered.\n"
                "We generally recommend altering this or temperature but not both.",
            ),
            Slider(
                id="frequency_penalty",
                label="frequency_penalty",
                initial=settings.get("frequency_penalty"),
                min=0,
                max=2,
                step=0.01,
                tooltip=
                "Number between -2.0 and 2.0. Positive values penalize new tokens based on their existing "
                "frequency in the text so far, decreasing the model's likelihood to repeat the same line verbatim.",
            ),
            Slider(
                id="presence_penalty",
                label="presence_penalty",
                initial=settings.get("presence_penalty"),
                min=-2,
                max=2,
                step=0.01,
                tooltip=
                "Number between -2.0 and 2.0. Positive values penalize new tokens based on whether they appear "
                "in the text so far, increasing the model's likelihood to talk about new topics.",
            ),
            Tags(
                id="stop",
                label="stop",
                initial=settings.get("stop"),
                values=[],
                tooltip=
                "Up to 4 sequences where the API will stop generating further tokens. "
                "The returned text will not contain the stop sequence.",
            )
        ]
    )
    return chat_settings


@cl.on_chat_start
async def start():
    cl.user_session.set("message_history", [], )
    if cl.user_session.get("chat_settings"):
        init_settings = cl.user_session.get("chat_settings")
    else:
        base_url = "https://api.openai.com/v1"
        cl.user_session.set("base_url", base_url)
        init_settings = {
            "base_url": base_url,
            "http_proxy": None,
            "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "models": openai_models,
            "stream": True,
            "max_tokens": 512,
            "temperature": 0.7,
            "top_p": 0.3,
            "frequency_penalty": 0.7,
            "presence_penalty": 0.4,
            "stop": [],
        }
    chat_settings = await create_settings(init_settings)
    settings = await chat_settings.send()
    cl.user_session.set("chat_settings", settings)


@cl.on_settings_update
async def settings_update(settings):
    base_url = cl.user_session.get("base_url")
    print(f"base_url: {base_url}")
    base_url_update = settings.get("base_url")
    print(f"base_url_update: {base_url_update}")
    # If the API address changes, retrieve the model list again.
    if base_url != base_url_update:
        api_key = settings.get('api_key')
        http_proxy = settings.get('http_proxy')
        client = await create_client(base_url_update, api_key, http_proxy)
        models = await get_model_list(client)
        settings["models"] = models
        chat_settings = await create_settings(settings)
        await chat_settings.send()
        cl.user_session.set("base_url", base_url_update)
    cl.user_session.set("settings", settings)
    print("on_settings_update", settings)


@cl.on_message
async def main(message: cl.Message):
    message_history = cl.user_session.get("message_history")
    message_history.append({"role": "user", "content": message.content})

    msg = cl.Message(content="")
    await msg.send()

    chat_settings = cl.user_session.get("chat_settings")
    print(chat_settings)
    settings = chat_settings.copy()
    base_url = settings.pop('base_url')
    api_key = settings.pop('api_key')
    http_proxy = settings.pop('http_proxy')
    print(settings)
    client = await create_client(base_url, api_key, http_proxy)

    completion = await client.chat.completions.create(
        messages=message_history, **settings
    )
    stream = settings.get('stream')
    if stream:
        async for part in completion:
            if token := part.choices[0].delta.content or "":
                await msg.stream_token(token)
    else:
        content = completion.choices[0].message.content
        msg = cl.Message(content=content)
        await msg.send()

    message_history.append({"role": "assistant", "content": msg.content})
    await msg.update()
