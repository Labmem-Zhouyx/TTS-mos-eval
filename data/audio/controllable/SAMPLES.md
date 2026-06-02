# Controllable 评测用例清单

对比系统（每个样本目录下各放一个同名 `.wav`）：

| 文件名 | 系统 |
| --- | --- |
| `VoxCPM2.wav` | VoxCPM2 |
| `VoiceSculptor.wav` | VoiceSculptor |
| `Qwen3-TTS-VD.wav` | Qwen3-TTS-VD |
| `MOSS-VoiceGenerator.wav` | MOSS-VoiceGenerator |

合成时：**Instruction** 作为控制/风格指令，**Content** 为 `meta.json` 中的 `text` 字段。

> 扫描器仅加载目录内至少有一个 `.wav` 的样本；放入音频后刷新服务即可出现在面板中。

## English（`sample_en_001` … `sample_en_010`）

| # | 目录 | Instruction | Content (`text`) |
| --- | --- | --- | --- |
| 1 | `sample_en_001` | Speak in a warm, gentle, and slightly emotional female voice, as if comforting a close friend. | Don't worry, everything is going to be alright. You've been so strong, and I'm really proud of you. |
| 2 | `sample_en_002` | Use an energetic, enthusiastic young male voice with fast pace and rising intonation, like a motivational speaker. | Today is the day you change your life! Take that first step, believe in yourself, and watch miracles happen! |
| 3 | `sample_en_003` | Narrate in a calm, deep, mysterious male voice with slow pace and slight suspense, like a thriller storyteller. | The old house stood silent at the end of the street. But as the clock struck midnight, something inside began to move. |
| 4 | `sample_en_004` | Speak in a professional, confident female news anchor voice, clear and neutral. | Good evening. In today's top story, scientists have announced a major breakthrough in renewable energy technology. |
| 5 | `sample_en_005` | Use a cute, playful, child-like female voice with high pitch and excitement. | Look! The butterfly is so beautiful! Can we follow it and see where it goes? |
| 6 | `sample_en_006` | Elderly gentleman voice, warm, wise, and slightly slow, like a grandfather telling a story. | When I was your age, we didn't have all these fancy gadgets. But we had something much more valuable — time for each other. |
| 7 | `sample_en_007` | Sarcastic, witty, young adult male voice with dry humor. | Oh sure, because waking up at 6 AM for a meeting that could have been an email is exactly how I wanted to start my day. |
| 8 | `sample_en_008` | Passionate, inspiring female voice with strong emotion, like a TED speaker. | Every failure is not the end of your story — it is merely the beginning of a much more interesting chapter. |
| 9 | `sample_en_009` | Romantic, soft, and affectionate female voice, gentle and intimate. | Every time I look at you, I fall in love all over again. You make my world feel complete. |
| 10 | `sample_en_010` | Authoritative, strict but fair male professor voice, academic tone. | Understanding quantum mechanics requires not just intelligence, but also the courage to question everything you think you know. |

## Chinese（`sample_zh_001` … `sample_zh_010`，对应原稿 11–20）

| # | 目录 | Instruction | Content (`text`) |
| --- | --- | --- | --- |
| 11 | `sample_zh_001` | 用温柔体贴的年轻女性声音，带着关怀和温暖，像在安慰失恋的朋友。 | 别难过了，这不是你的错。你值得被更好的人珍惜，相信我，明天一定会更好。 |
| 12 | `sample_zh_002` | 用充满激情和动力的年轻男性声音，语速稍快，富有感染力，像励志演讲。 | 不要害怕失败！每一次跌倒都是为了让你站得更高。相信自己，你一定可以做到！ |
| 13 | `sample_zh_003` | 用低沉神秘的男性声音，语速缓慢，带有悬疑感，像在讲恐怖故事。 | 那座老房子已经空置多年了……可每当午夜来临，楼上总会传来奇怪的脚步声。 |
| 14 | `sample_zh_004` | 用专业清晰的女主播声音，语调平稳客观，像播报新闻。 | 各位观众朋友晚上好。今天，人工智能领域再次取得重大突破，一项新算法将大幅提升机器翻译的准确率。 |
| 15 | `sample_zh_005` | 用可爱活泼的女孩声音，语调上扬，充满童趣。 | 哇！这只小猫好软好萌哦！我们可以给它取个名字吗？就叫它小奶球好不好？ |
| 16 | `sample_zh_006` | 用慈祥稳重的老年男性声音，语速稍慢，充满人生智慧。 | 孩子啊，人生最重要的是心安。钱可以再赚，但陪伴和健康，一旦失去了就再也回不来了。 |
| 17 | `sample_zh_007` | 用略带讽刺、幽默的年轻男性声音，语气轻松调侃。 | 行吧，又是周一。又要为了那点工资假装很热爱这份工作了，真的是太敬业了。 |
| 18 | `sample_zh_008` | 用富有感染力的女性声音，情感真挚，像在做励志分享。 | 无论你现在经历什么，请记住：所有黑暗都是为了让你更加珍惜后来的光芒。 |
| 19 | `sample_zh_009` | 用温柔浪漫的女性声音，轻柔亲密，像在对恋人说话。 | 遇见你以后，我才知道原来每天醒来都可以这么幸福。谢谢你出现在我的生命里。 |
| 20 | `sample_zh_010` | 用严谨权威的男性教授声音，学术且富有条理。 | 在科学研究中，重要的不是你知道什么，而是你愿意质疑什么。只有不断挑战现有认知，我们才能真正向前迈进。 |
