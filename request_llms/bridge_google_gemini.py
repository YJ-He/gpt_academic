# encoding: utf-8
# @Time   : 2023/12/21
# @Author : Spike
# @Descr   :
import json
import re
import os
import time
from request_llms.com_google import GoogleChatInit
from toolbox import ChatBotWithCookies
from toolbox import get_conf, update_ui, update_ui_latest_msg, have_any_recent_upload_image_files, trimmed_format_exc, log_chat, encode_image

proxies, TIMEOUT_SECONDS, MAX_RETRY = get_conf('proxies', 'TIMEOUT_SECONDS', 'MAX_RETRY')
timeout_bot_msg = '[Local Message] Request timeout. Network error. Please check proxy settings in config.py.' + \
                  '网络错误，检查代理服务器是否可用，以及代理设置的格式是否正确，格式须是[协议]://[地址]:[端口]，缺一不可。'


def predict_no_ui_long_connection(inputs:str, llm_kwargs:dict, history:list=[], sys_prompt:str="", observe_window:list=[],
                                  console_silence:bool=False):
    # 检查API_KEY
    if get_conf("GEMINI_API_KEY") == "":
        raise ValueError(f"请配置 GEMINI_API_KEY。")

    # 修改 llm_kwargs，添加或修正 stopSequences 参数
    if 'stopSequences' not in llm_kwargs:
        llm_kwargs['stopSequences'] = 1  # 设置为有效值 (1-16)
    elif llm_kwargs['stopSequences'] == 0:
        llm_kwargs['stopSequences'] = 1  # 如果是0，修正为有效值
        
    genai = GoogleChatInit(llm_kwargs)
    watch_dog_patience = 5  # 看门狗的耐心, 设置5秒即可
    gpt_replying_buffer = ''
    stream_response = genai.generate_chat(inputs, llm_kwargs, history, sys_prompt)
    for response in stream_response:
        results = response.decode()
        match = re.search(r'"text":\s*"((?:[^"\\]|\\.)*)"', results, flags=re.DOTALL)
        error_match = re.search(r'\"message\":\s*\"(.*?)\"', results, flags=re.DOTALL)
        if match:
            try:
                paraphrase = json.loads('{"text": "%s"}' % match.group(1))
            except:
                raise ValueError(f"解析GEMINI消息出错。")
            buffer = paraphrase['text']
            gpt_replying_buffer += buffer
            if len(observe_window) >= 1:
                observe_window[0] = gpt_replying_buffer
            if len(observe_window) >= 2:
                if (time.time() - observe_window[1]) > watch_dog_patience: raise RuntimeError("程序终止。")
        if error_match:
            raise RuntimeError(f'{gpt_replying_buffer} 对话错误')
    return gpt_replying_buffer

def make_media_input(inputs, image_paths):
    image_base64_array = []
    for image_path in image_paths:
        path = os.path.abspath(image_path)
        inputs = inputs + f'<br/><br/><div align="center"><img src="file={path}"></div>'
        base64 = encode_image(path)
        image_base64_array.append(base64)
    return inputs, image_base64_array

def predict(inputs:str, llm_kwargs:dict, plugin_kwargs:dict, chatbot:ChatBotWithCookies,
            history:list=[], system_prompt:str='', stream:bool=True, additional_fn:str=None):
    
    from .bridge_all import model_info

    # 检查API_KEY
    if get_conf("GEMINI_API_KEY") == "":
        yield from update_ui_latest_msg(f"请配置 GEMINI_API_KEY。", chatbot=chatbot, history=history, delay=0)
        return

    # 适配润色区域
    if additional_fn is not None:
        from core_functional import handle_core_functionality
        inputs, history = handle_core_functionality(additional_fn, inputs, history, chatbot)

    # multimodal capacity
    # inspired by codes in bridge_chatgpt
    has_multimodal_capacity = model_info[llm_kwargs['llm_model']].get('has_multimodal_capacity', False)
    if has_multimodal_capacity:
        has_recent_image_upload, image_paths = have_any_recent_upload_image_files(chatbot, pop=True)
    else:
        has_recent_image_upload, image_paths = False, []
    if has_recent_image_upload:
        inputs, image_base64_array = make_media_input(inputs, image_paths)
    else:
        inputs, image_base64_array = inputs, []

    chatbot.append((inputs, ""))
    yield from update_ui(chatbot=chatbot, history=history)
    genai = GoogleChatInit(llm_kwargs)
    retry = 0
    while True:
        try:
            stream_response = genai.generate_chat(inputs, llm_kwargs, history, system_prompt, image_base64_array, has_multimodal_capacity)
            break
        except Exception as e:
            retry += 1
            chatbot[-1] = ((chatbot[-1][0], trimmed_format_exc()))
            yield from update_ui(chatbot=chatbot, history=history, msg="请求失败")  # 刷新界面
            return
    gpt_replying_buffer = ""
    gpt_security_policy = ""
    history.extend([inputs, ''])
    for response in stream_response:
        results = response.decode("utf-8")    # 被这个解码给耍了。。
        gpt_security_policy += results
        match = re.search(r'"text":\s*"((?:[^"\\]|\\.)*)"', results, flags=re.DOTALL)
        error_match = re.search(r'\"message\":\s*\"(.*)\"', results, flags=re.DOTALL)
        if match:
            try:
                paraphrase = json.loads('{"text": "%s"}' % match.group(1))
            except:
                raise ValueError(f"解析GEMINI消息出错。")
            gpt_replying_buffer += paraphrase['text']    # 使用 json 解析库进行处理
            chatbot[-1] = (inputs, gpt_replying_buffer)
            history[-1] = gpt_replying_buffer
            log_chat(llm_model=llm_kwargs["llm_model"], input_str=inputs, output_str=gpt_replying_buffer)
            yield from update_ui(chatbot=chatbot, history=history)
        if error_match:
            # history = history[-2]  # 错误的不纳入对话
            # chatbot[-1] = (inputs, gpt_replying_buffer + f"对话错误，请查看message\n\n```\n{error_match.group(1)}\n```")
            # yield from update_ui(chatbot=chatbot, history=history)
            # raise RuntimeError('对话错误')
            try:
                # Update history safely
                if len(history) >= 2:
                    history = history[:-2]  # Remove last two entries instead of direct indexing
                
                # Construct complete error message
                error_message = f"对话错误: {error_match.group(1) if error_match else '未知错误'}"
                
                # Update chatbot with error info
                chatbot[-1] = (inputs, gpt_replying_buffer + f"\n\n```\n{error_message}\n```")
                
                # Yield UI update instead of raising exception
                yield from update_ui(chatbot=chatbot, history=history, msg=error_message)
                return
            except Exception as e:
                # Catch any other errors during error handling
                error_message = f"处理错误信息时发生异常: {str(e)}"
                chatbot[-1] = (inputs, error_message)
                yield from update_ui(chatbot=chatbot, history=history, msg=error_message)
                return
    if not gpt_replying_buffer:
        history = history[-2]  # 错误的不纳入对话
        chatbot[-1] = (inputs, gpt_replying_buffer + f"触发了Google的安全访问策略，没有回答\n\n```\n{gpt_security_policy}\n```")
        yield from update_ui(chatbot=chatbot, history=history)


if __name__ == '__main__':
    import sys
    llm_kwargs = {'llm_model': 'gemini-pro'}
    result = predict('Write long a story about a magic backpack.', llm_kwargs, llm_kwargs, [])
    for i in result:
        print(i)
