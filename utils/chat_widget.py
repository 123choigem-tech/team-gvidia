import streamlit as st


def inject():
    api_key = st.secrets.get("OPENAI_API_KEY", "")

    st.markdown(f"""
<iframe srcdoc="
<script>
(function() {{
  var doc = window.parent.document;
  if (doc.getElementById('chat-fab')) return;

  var style = doc.createElement('style');
  style.textContent = \`
    #chat-fab {{
      position: fixed !important;
      right: 28px !important;
      bottom: 32px !important;
      width: 56px !important;
      height: 56px !important;
      border-radius: 50% !important;
      background: linear-gradient(135deg,#005f6e,#00c2d4) !important;
      color: white !important;
      font-size: 26px !important;
      border: none !important;
      cursor: pointer !important;
      box-shadow: 0 4px 20px rgba(0,194,212,0.45) !important;
      z-index: 999999 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      transition: transform .2s, box-shadow .2s !important;
    }}
    #chat-fab:hover {{ transform:scale(1.1) !important; }}
    #chat-panel {{
      position: fixed !important;
      top: 0 !important;
      right: -400px !important;
      width: 380px !important;
      height: 100vh !important;
      background: #020d1a !important;
      z-index: 999998 !important;
      display: flex !important;
      flex-direction: column !important;
      border-left: 1px solid rgba(0,194,212,0.15) !important;
      box-shadow: -4px 0 40px rgba(0,0,0,0.5) !important;
      transition: right .3s cubic-bezier(.4,0,.2,1) !important;
    }}
    #chat-panel.open {{ right: 0 !important; }}
    #chat-head {{
      background:#041529;color:#e8f4f8;padding:16px 20px;
      font-weight:700;font-size:15px;
      display:flex;justify-content:space-between;align-items:center;
      border-bottom:1px solid rgba(0,194,212,0.12);flex-shrink:0;
      font-family:'Noto Sans KR',sans-serif;
    }}
    #chat-x {{background:none;border:none;color:#7aacbf;font-size:20px;cursor:pointer;}}
    #chat-x:hover{{color:#00e5ff;}}
    #chat-msgs {{
      flex:1;overflow-y:auto;padding:14px;
      display:flex;flex-direction:column;gap:9px;
    }}
    #chat-msgs::-webkit-scrollbar{{width:4px;}}
    #chat-msgs::-webkit-scrollbar-thumb{{background:rgba(0,194,212,0.2);border-radius:4px;}}
    .cm-user {{
      background:linear-gradient(135deg,#005f6e,#00a896);color:white;
      padding:9px 13px;border-radius:14px 14px 4px 14px;
      font-size:13px;line-height:1.6;align-self:flex-end;
      max-width:83%;word-break:keep-all;font-family:'Noto Sans KR',sans-serif;
    }}
    .cm-bot {{
      background:rgba(0,194,212,0.07);color:#c8e6f0;
      padding:9px 13px;border-radius:14px 14px 14px 4px;
      font-size:13px;line-height:1.6;align-self:flex-start;
      max-width:83%;border:1px solid rgba(0,194,212,0.1);
      word-break:keep-all;font-family:'Noto Sans KR',sans-serif;
    }}
    .cm-thinking{{color:#3a6a7a;font-style:italic;}}
    #chat-row {{
      display:flex;padding:11px 13px;gap:8px;
      border-top:1px solid rgba(0,194,212,0.1);
      background:#041529;flex-shrink:0;
    }}
    #chat-inp {{
      flex:1;background:rgba(0,194,212,0.06);
      border:1px solid rgba(0,194,212,0.18);border-radius:10px;
      padding:9px 13px;font-size:13px;color:#e8f4f8;outline:none;
      font-family:'Noto Sans KR',sans-serif;
    }}
    #chat-inp:focus{{border-color:#00c2d4;background:rgba(0,194,212,0.1);}}
    #chat-inp::placeholder{{color:rgba(200,230,240,0.3);}}
    #chat-btn {{
      background:linear-gradient(135deg,#005f6e,#00c2d4);
      color:white;border:none;border-radius:10px;
      padding:9px 15px;cursor:pointer;font-size:14px;font-weight:700;
      font-family:'Noto Sans KR',sans-serif;
    }}
    #chat-btn:hover{{opacity:.85;}}
  \`;
  doc.head.appendChild(style);

  var fab = doc.createElement('button');
  fab.id = 'chat-fab';
  fab.innerHTML = '💬';
  doc.body.appendChild(fab);

  var panel = doc.createElement('div');
  panel.id = 'chat-panel';
  panel.innerHTML = \`
    <div id='chat-head'>
      🌊 고수온 AI 챗봇
      <button id='chat-x'>✕</button>
    </div>
    <div id='chat-msgs'>
      <div class='cm-bot'>안녕하세요! 고수온 분석 챗봇입니다.<br>관심지역, 수온 데이터, 분석 결과에 대해 질문하세요.</div>
    </div>
    <div id='chat-row'>
      <input id='chat-inp' type='text' placeholder='질문을 입력하세요...'/>
      <button id='chat-btn'>전송</button>
    </div>
  \`;
  doc.body.appendChild(panel);

  var history = [
    {{role:'system',content:'당신은 고수온 연안재해 모니터링 시스템의 해양 기상 전문 AI입니다. 한국어로 간결하게 답하세요.'}}
  ];

  fab.onclick = function(){{
    panel.classList.toggle('open');
    fab.innerHTML = panel.classList.contains('open') ? '✕' : '💬';
  }};
  doc.getElementById('chat-x').onclick = function(){{
    panel.classList.remove('open'); fab.innerHTML='💬';
  }};

  async function send(){{
    var inp = doc.getElementById('chat-inp');
    var msgs = doc.getElementById('chat-msgs');
    var text = inp.value.trim();
    if(!text) return;
    inp.value='';
    msgs.innerHTML += '<div class=\\'cm-user\\'>' + text + '</div>';
    var el = doc.createElement('div');
    el.className='cm-bot cm-thinking'; el.id='cm-load'; el.textContent='분석 중...';
    msgs.appendChild(el); msgs.scrollTop=msgs.scrollHeight;
    history.push({{role:'user',content:text}});
    try{{
      var res = await fetch('https://api.openai.com/v1/chat/completions',{{
        method:'POST',
        headers:{{'Content-Type':'application/json','Authorization':'Bearer {api_key}'}},
        body:JSON.stringify({{model:'gpt-4o-mini',messages:history,max_tokens:512}})
      }});
      var data = await res.json();
      var reply = data.choices[0].message.content;
      history.push({{role:'assistant',content:reply}});
      var l=doc.getElementById('cm-load');
      if(l){{l.className='cm-bot';l.removeAttribute('id');l.innerHTML=reply.replace(/\\n/g,'<br>');}}
    }}catch(e){{
      var l=doc.getElementById('cm-load');
      if(l){{l.className='cm-bot';l.removeAttribute('id');l.textContent='⚠️ '+e.message;}}
    }}
    msgs.scrollTop=msgs.scrollHeight;
  }}

  doc.getElementById('chat-btn').onclick=send;
  doc.getElementById('chat-inp').addEventListener('keydown',function(e){{if(e.key==='Enter')send();}});
}})();
</script>
" style="display:none" width="0" height="0"></iframe>
""", unsafe_allow_html=True)
