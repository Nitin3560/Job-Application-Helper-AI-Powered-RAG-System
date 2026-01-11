from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings

def main():
    Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
    vec = Settings.embed_model.get_text_embedding("hello how you guyss doing, it comedy shorts gamer here")
    print("Embedding length:", len(vec))
    print("First 5 values:", vec[:5])

if __name__ == "__main__":
    main()
