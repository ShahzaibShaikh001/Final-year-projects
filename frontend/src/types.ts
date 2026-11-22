export type Paper = {
  title: string;
  authors?: string;
  year?: number | null;
  abstract?: string;
  source?: string;
  url?: string;
  pdf_url?: string;
  doi?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  kind?: string;
  topics?: string[];
  papers?: Paper[];
};

export type Conversation = {
  id: string;
  title: string;
  messages: ChatMessage[];
  selectedPaper: Paper | null;
};
