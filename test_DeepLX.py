import httpx, json

deeplx_api = "http://127.0.0.1:1188/translate"

# data = {
#     "text": [
#         "you will submit the above job script with a time limit of 30 minutes. The acceptable time formats include 'minutes', 'minutes:seconds', 'hours:minutes:seconds', 'days-hours', 'days-hours:minutes' and 'days-hours:minutes:seconds'. Please note that the time limit will strongly affect how quickly the job is started, since longer jobs are eligible to run on fewer nodes."
#     ],
#     "target_lang": "zh"
# }

data = {
	"text": "you will submit the above job script with a time limit of 30 minutes. The acceptable time formats include 'minutes', 'minutes:seconds', 'hours:minutes:seconds', 'days-hours', 'days-hours:minutes' and 'days-hours:minutes:seconds'. Please note that the time limit will strongly affect how quickly the job is started, since longer jobs are eligible to run on fewer nodes.",
	"source_lang": "EN",
	"target_lang": "ZH"
}

post_data = json.dumps(data)
r = httpx.post(url=deeplx_api, data=post_data).text
print(r)
