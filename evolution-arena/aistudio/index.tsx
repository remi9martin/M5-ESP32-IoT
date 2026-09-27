// AI Studio bridge: lets the arena call Gemini with the key AI Studio provides,
// so nothing has to be pasted into the page.
import { GoogleGenAI } from '@google/genai';

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY as string });

(window as any).arenaLLM = async (model: string, parts: unknown[], schema: unknown, temperature: number) => {
  const res = await ai.models.generateContent({
    model,
    contents: [{ role: 'user', parts: parts as any }],
    config: { temperature, responseMimeType: 'application/json', responseSchema: schema as any },
  });
  if (!res.text) throw new Error('Empty response: ' + (res.candidates?.[0]?.finishReason ?? 'unknown'));
  return res.text;
};

const key = document.getElementById('apiKey') as HTMLInputElement | null;
if (key) key.placeholder = 'Using the AI Studio key (leave empty)';
