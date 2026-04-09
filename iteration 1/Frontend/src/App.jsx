import{useState}from"react";
import"./App.css";
import{useEffect,useRef}from"react";

function App(){
  const[messages,setMessages]=useState([
    {role:"assistant",content:"Hello !!"},
  ]);
  const[input,setInput]=useState("");
  const[sending,setSending]=useState(false);
  const[status,setStatus]=useState("");
  const handleSend=async()=>{
    const text=input.trim();
    if(!text||sending)return;
    setInput("");
    setSending(true)
    setMessages((prev)=>[...prev,{role:"user",content:text}]);

    try{
      const res=await fetch("http://127.0.0.1:8000/chat",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ message: text }),
      });
      if(!res.ok){
        const t=await res.text();
        throw new Error(t||"Chat failed");
      }
      const data=await res.json();
      setTimeout(()=>setStatus(""),2000);
    
      const clean = (data.reply || "")
        .replace(/according to the sources.*?,/i,"")
        .replace(/\[[^\]]+\]/g,"")
        .trim();
    
      setMessages(p=>[...p,{role:"assistant",content:clean}]);
    
    }catch (e) {
      const msg = e?.message || "Request failed";
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${msg}` }]);
    } finally {
      setSending(false);
    }      
  };
  const endRef=useRef(null);
  useEffect(()=>{endRef.current?.scrollIntoView({behavior:"smooth"});},[messages]);

  const uploadFile=async(file)=>{
    try{
      setStatus("Uploading...");
      const formData=new FormData();
      formData.append("file",file);
      const res=await fetch("http://127.0.0.1:8000/upload",{
        method:"POST",
        body:formData,
      });

      if(!res.ok){
        const text=await res.text();
        throw new Error(text||"Upload failed");
      }
      const data=await res.json();
      setStatus(`File uploaded:${data.filename}`);
      setTimeout(()=>setStatus(""),2000);
    }catch(err){
      setStatus(`Upload error:${err.message}`);
      setTimeout(()=>setStatus(""),2000);
    }
  };
  const TypingDots = () => (
    <span className="typing-dots" aria-label="Generating">
      <span>.</span><span>.</span><span>.</span>
    </span>
  );
  

  return(
    <div className="page">
      <div>
        <div className="chatbox">
          <div className="chat-header">Job Application Helper</div>

          <div className="chat-messages">
  {messages.map((m, i) => (
    <div
      key={i}
      className={`msg ${m.role === "user" ? "user" : "assistant"}`}
    >
      {m.content}
    </div>
  ))}

  {/* ✅ dots appear as NEXT assistant message */}
  {sending && (
    <div className="msg assistant">
      <span className="typing-dots" aria-label="Generating">
        <span>.</span><span>.</span><span>.</span>
      </span>
    </div>
  )}

  <div ref={endRef} />
</div>



          <div className="chat-input">
            <div
              className="upload-btn"
              onClick={()=>document.getElementById("fileInput").click()}
              title="Choose file"
            >
              +
            </div>

            <input
              id="fileInput"
              type="file"
              accept=".txt,.pdf"
              style={{display:"none"}}
              onChange={(e)=>{
                const file=e.target.files?.[0];
                if(file){
                  uploadFile(file);
                  e.target.value="";
                }
              }}
            />

            <input
              type="text"
              placeholder="Type a message..."
              value={input}
              onChange={(e)=>setInput(e.target.value)}
              onKeyDown={(e)=>{
                if(e.key==="Enter")handleSend();
              }}
            />

            <button onClick={handleSend} disabled={sending}>
              Send
            </button>
          </div>
        </div>

        {status&&<div className="below-status">{status}</div>}
      </div>
    </div>
  );
}

export default App;
