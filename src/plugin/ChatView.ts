import { ItemView, WorkspaceLeaf, Notice, MarkdownRenderer } from 'obsidian';
import LabAgentPlugin from './main';

export const VIEW_TYPE_CHAT = 'lab-agent-chat-view';

export class ChatView extends ItemView {
	plugin: LabAgentPlugin;
	
	// Containers for tabs
	tabContainer: HTMLElement;
	syncTabContent: HTMLElement;
	chatTabContent: HTMLElement;
	qaTabContent: HTMLElement;

	// Chat elements
	messageContainer: HTMLElement;
	scopeSelect: HTMLSelectElement;
	strategySelect: HTMLSelectElement;
	inputEl: HTMLTextAreaElement;
	sendBtn: HTMLButtonElement;
	
	// Sync elements
	cloudStatusContainer: HTMLElement;
	cloudTreeContainer: HTMLElement;

	// QA elements
	qaListContainer: HTMLElement;
	qaInputEl: HTMLTextAreaElement;
	qaSubmitBtn: HTMLButtonElement;

	constructor(leaf: WorkspaceLeaf, plugin: LabAgentPlugin) {
		super(leaf);
		this.plugin = plugin;
	}

	getViewType() {
		return VIEW_TYPE_CHAT;
	}

	getDisplayText() {
		return 'Lab AI Copilot';
	}

	getIcon(): string {
		return 'bot';
	}

	async onOpen() {
		const container = this.containerEl.children[1];
		container.empty();
		container.addClass('lab-chat-container');

		// 1. Build Tab Header
		this.tabContainer = container.createEl('div', { cls: 'lab-tab-header' });
		const tabSync = this.tabContainer.createEl('div', { text: '☁️ 云端同步', cls: 'lab-tab active' });
		const tabChat = this.tabContainer.createEl('div', { text: '🤖 AI 问答', cls: 'lab-tab' });
		const tabQA = this.tabContainer.createEl('div', { text: '💬 社区解答', cls: 'lab-tab' });

		// 2. Build Tab Contents
		this.syncTabContent = container.createEl('div', { cls: 'lab-tab-content active' });
		this.chatTabContent = container.createEl('div', { cls: 'lab-tab-content' });
		this.qaTabContent = container.createEl('div', { cls: 'lab-tab-content' });

		// -- Setup Sync Tab --
		this.buildSyncTab();

		// -- Setup Chat Tab --
		this.buildChatTab();

		// -- Setup QA Tab --
		this.buildQATab();

		// Tab Switching Logic
		tabSync.onclick = () => { this.switchTab(tabSync, this.syncTabContent); this.refreshCloudStatus(); };
		tabChat.onclick = () => this.switchTab(tabChat, this.chatTabContent);
		tabQA.onclick = () => { this.switchTab(tabQA, this.qaTabContent); this.refreshQAList(); };

		// Initial load: Force auto-sync cloud and QA
		this.refreshCloudStatus();
		this.plugin.syncToLabCloud();
		this.refreshQAList();
	}

	switchTab(activeTabEl: HTMLElement, activeContentEl: HTMLElement) {
		// Reset all tabs
		this.tabContainer.querySelectorAll('.lab-tab').forEach(el => el.removeClass('active'));
		this.syncTabContent.removeClass('active');
		this.chatTabContent.removeClass('active');
		this.qaTabContent.removeClass('active');

		// Set active
		activeTabEl.addClass('active');
		activeContentEl.addClass('active');
	}

	/* =======================================
	   SYNC TAB
	   ======================================= */
	buildSyncTab() {
		const syncBtn = this.syncTabContent.createEl('button', { text: '🚀 上传本地知识库至云端', cls: 'lab-big-btn' });
		syncBtn.onclick = async () => {
			syncBtn.disabled = true;
			syncBtn.innerText = '上传中...';
			await this.plugin.syncToLabCloud();
			syncBtn.innerText = '🚀 上传本地知识库至云端';
			syncBtn.disabled = false;
			this.refreshCloudStatus();
		};

		this.syncTabContent.createEl('h3', { text: '课题组成员云端总库状态' });
		this.cloudStatusContainer = this.syncTabContent.createEl('div', { cls: 'lab-cloud-list' });
		
		this.syncTabContent.createEl('h3', { text: '☁️ 我的云端知识树', cls: 'lab-tree-title' });
		this.cloudTreeContainer = this.syncTabContent.createEl('div', { cls: 'lab-tree-container' });
	}

	async refreshCloudStatus() {
		this.cloudStatusContainer.empty();
		this.cloudStatusContainer.createEl('div', { text: '加载中...', cls: 'lab-loading-text' });

		try {
			const res = await fetch(`${this.plugin.settings.serverUrl}/api/upload/status`);
			if (!res.ok) throw new Error();
			const data = await res.json();
			const members = data.members || [];
			
			this.cloudStatusContainer.empty();
			if (members.length === 0) {
				this.cloudStatusContainer.createEl('div', { text: '目前云端数据库为空。', cls: 'lab-empty-text' });
				return;
			}

			members.forEach((m: any) => {
				const card = this.cloudStatusContainer.createEl('div', { cls: 'lab-member-card' });
				card.createEl('div', { text: `👤 ${m.username}`, cls: 'lab-member-name' });
				card.createEl('div', { text: `已上传文档: ${m.total_docs} 篇`, cls: 'lab-member-meta' });
				card.createEl('div', { text: `最后同步: ${m.last_sync}`, cls: 'lab-member-meta' });
			});
		} catch (e) {
			this.cloudStatusContainer.empty();
			this.cloudStatusContainer.createEl('div', { text: '无法连接到云端服务，请检查后端是否运行。', cls: 'lab-error-text' });
		}
		
		await this.refreshCloudTree();
	}

	async refreshCloudTree() {
		this.cloudTreeContainer.empty();
		this.cloudTreeContainer.createEl('div', { text: '正在拉取云端结构...', cls: 'lab-loading-text' });

		try {
			const res = await fetch(`${this.plugin.settings.serverUrl}/api/upload/tree/${this.plugin.settings.username}`);
			if (!res.ok) throw new Error();
			const data = await res.json();
			
			this.cloudTreeContainer.empty();
			if (!data.tree || data.tree.length === 0) {
				this.cloudTreeContainer.createEl('div', { text: '您的云端暂无数据。', cls: 'lab-empty-text' });
				return;
			}
			
			this.renderTree(data.tree, this.cloudTreeContainer);
		} catch (e) {
			this.cloudTreeContainer.empty();
			this.cloudTreeContainer.createEl('div', { text: '获取树状结构失败。', cls: 'lab-error-text' });
		}
	}

	renderTree(nodes: any[], container: HTMLElement, isRoot: boolean = true) {
		const ul = container.createEl('ul', { cls: 'lab-tree-ul' });
		if (!isRoot) {
			ul.style.display = 'none'; // Collapse all non-root folders by default
		}
		for (const node of nodes) {
			const li = ul.createEl('li', { cls: 'lab-tree-li' });
			if (node.type === 'folder') {
				const folderDiv = li.createEl('div', { text: `▶ 📁 ${node.name}`, cls: 'lab-tree-node folder' });
				folderDiv.style.cursor = 'pointer';
				let childrenUl: HTMLElement | null = null;
				if (node.children && node.children.length > 0) {
					childrenUl = this.renderTree(node.children, li, false);
				}
				folderDiv.onclick = () => {
					let isExpanded = folderDiv.innerText.startsWith('▼');
					if (!isExpanded) {
						if (childrenUl) childrenUl.style.display = 'block';
						folderDiv.innerText = `▼ 📂 ${node.name}`;
					} else {
						if (childrenUl) childrenUl.style.display = 'none';
						folderDiv.innerText = `▶ 📁 ${node.name}`;
					}
				};
			} else {
				li.createEl('div', { text: `📄 ${node.name}`, cls: 'lab-tree-node file' });
			}
		}
		return ul;
	}

	/* =======================================
	   CHAT TAB
	   ======================================= */
	sessionSelect: HTMLSelectElement;

	updateSessionSelect() {
		if (!this.sessionSelect) return;
		this.sessionSelect.empty();
		const sessions = this.plugin.settings.sessions || {};
		const sortedIds = Object.keys(sessions).sort((a, b) => sessions[b].updatedAt - sessions[a].updatedAt);
		for (const id of sortedIds) {
			const s = sessions[id];
			this.sessionSelect.createEl('option', { value: id, text: s.title || '新对话' });
		}
		this.sessionSelect.value = this.plugin.settings.sessionId;
	}

	renderCurrentSession() {
		this.messageContainer.empty();
		const session = this.plugin.settings.sessions[this.plugin.settings.sessionId];
		if (session && session.history && session.history.length > 0) {
			for (const msg of session.history) {
				if (msg.role === 'ai') {
					this.addMarkdownMessage(msg.content, 'ai', this.messageContainer);
				} else {
					this.addMessage(msg.content, 'user');
				}
			}
		} else {
			this.addMessage('我是课题组跨界检索 Agent。请选择检索范围后向我提问。', 'ai');
		}
	}

	buildChatTab() {
		// Header & Scope Selection
		const header = this.chatTabContent.createEl('div', { cls: 'lab-chat-header', attr: { style: 'display: flex; gap: 5px; flex-wrap: wrap; align-items: center;' } });
		
		this.strategySelect = header.createEl('select', { cls: 'lab-scope-select lab-strategy-select' });
		this.strategySelect.createEl('option', { value: 'agentic', text: '🧠 企业级双循环 (Agentic RAG)' });
		this.strategySelect.createEl('option', { value: 'vector', text: '🧲 语义模式 (Vector RAG)' });
		this.strategySelect.createEl('option', { value: 'graph', text: '🕸️ 拓扑模式 (Graph RAG)' });
		this.strategySelect.createEl('option', { value: 'bm25', text: '📚 字典模式 (BM25 RAG)' });

		this.scopeSelect = header.createEl('select', { cls: 'lab-scope-select' });
		this.scopeSelect.createEl('option', { value: 'global', text: '🌐 全局知识库 (Global)' });
		this.scopeSelect.createEl('option', { value: '李师姐', text: '👤 李师姐的笔记' });
		this.scopeSelect.createEl('option', { value: '王同学', text: '👤 王同学的笔记' });
		this.scopeSelect.createEl('option', { value: '张同学', text: '👤 张同学的笔记 (自己)' });

		this.strategySelect.onchange = () => this.retriggerSearch();
		this.scopeSelect.onchange = () => this.retriggerSearch();

		if (!this.plugin.settings.sessions) this.plugin.settings.sessions = {};
		
		this.sessionSelect = header.createEl('select', { cls: 'lab-scope-select', attr: { style: 'max-width: 120px;' } });
		this.updateSessionSelect();

		this.sessionSelect.onchange = async () => {
			const selectedId = this.sessionSelect.value;
			this.plugin.settings.sessionId = selectedId;
			await this.plugin.saveData(this.plugin.settings);
			this.renderCurrentSession();
		};

		const newChatBtn = header.createEl('button', { text: '🧹 新建对话', cls: 'lab-chat-send-btn', attr: { style: 'padding: 4px 8px;' } });
		newChatBtn.onclick = async () => {
			const newId = crypto.randomUUID();
			this.plugin.settings.sessionId = newId;
			this.plugin.settings.sessions[newId] = { title: '新对话', updatedAt: Date.now(), history: [] };
			await this.plugin.saveData(this.plugin.settings);
			this.updateSessionSelect();
			this.renderCurrentSession();
			this.addMessage('我是课题组跨界检索 Agent。后端原生记忆已刷新，请开启新的对话。', 'ai');
		};

		// Messages Area
		this.messageContainer = this.chatTabContent.createEl('div', { cls: 'lab-chat-messages' });
		
		if (!this.plugin.settings.sessionId || !this.plugin.settings.sessions[this.plugin.settings.sessionId]) {
			const newId = crypto.randomUUID();
			this.plugin.settings.sessionId = newId;
			this.plugin.settings.sessions[newId] = { title: '新对话', updatedAt: Date.now(), history: this.plugin.settings.chatHistory || [] };
			this.plugin.saveData(this.plugin.settings);
			this.updateSessionSelect();
		}

		this.renderCurrentSession();

		// Input Area
		const inputContainer = this.chatTabContent.createEl('div', { cls: 'lab-chat-input-container' });
		this.inputEl = inputContainer.createEl('textarea', { cls: 'lab-chat-input' });
		this.inputEl.placeholder = '向知识库提问...';
		this.inputEl.addEventListener('keydown', (e) => {
			if (e.key === 'Enter' && !e.shiftKey) {
				e.preventDefault();
				this.sendMessage();
			}
		});

		this.sendBtn = inputContainer.createEl('button', { text: '发送', cls: 'lab-chat-send-btn' });
		this.sendBtn.onclick = () => this.sendMessage();
	}

	async retriggerSearch() {
		// Only auto-retrigger if we aren't currently loading and there's a history
		if (this.sendBtn.disabled) return;
		
		const session = this.plugin.settings.sessions[this.plugin.settings.sessionId];
		if (!session || !session.history || session.history.length === 0) return;
		
		// Find the last user message
		let lastUserMsg = '';
		for (let i = session.history.length - 1; i >= 0; i--) {
			if (session.history[i].role === 'user') {
				lastUserMsg = session.history[i].content;
				break;
			}
		}
		
		if (!lastUserMsg) return;
		
		// Populate input and send it again
		this.inputEl.value = lastUserMsg;
		this.sendMessage();
	}

	async sendMessage() {
		const text = this.inputEl.value.trim();
		if (!text) return;

		this.inputEl.value = '';
		const scope = this.scopeSelect.value;
		this.addMessage(text, 'user');
		
		const session = this.plugin.settings.sessions[this.plugin.settings.sessionId];
		if (session) {
			session.history.push({ role: 'user', content: text });
			// Update title if it's a new chat
			if (session.history.length === 1) {
				session.title = text.substring(0, 10) + (text.length > 10 ? '...' : '');
				this.updateSessionSelect();
			}
		}
		await this.plugin.saveData(this.plugin.settings);

		this.inputEl.disabled = true;
		this.sendBtn.disabled = true;
		const loadingId = this.addLoadingIndicator(this.messageContainer);

		try {
			const res = await fetch(`${this.plugin.settings.serverUrl}/api/ai/chat`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ 
					query: text, 
					scope: scope, 
					strategy: this.strategySelect.value, 
					session_id: this.plugin.settings.sessionId 
				})
			});

			if (!res.ok) throw new Error(`Server returned ${res.status}`);
			const data = await res.json();
			const answer = data.reply || data.answer || data.result || '抱歉，后端未能返回有效内容。';
			
			this.removeLoadingIndicator(this.messageContainer, loadingId);
			try {
				await this.addMarkdownMessage(answer, 'ai', this.messageContainer);
			} catch (renderError) {
				const msgEl = this.messageContainer.createEl('div', { cls: 'lab-chat-message ai' });
				msgEl.innerText = answer;
				this.scrollToBottom(this.messageContainer);
			}
			
			const session = this.plugin.settings.sessions[this.plugin.settings.sessionId];
			if (session) {
				session.history.push({ role: 'ai', content: answer });
			}
			await this.plugin.saveData(this.plugin.settings);

		} catch (err) {
			this.removeLoadingIndicator(this.messageContainer, loadingId);
			this.addMessage(`⚠️ 网络请求错误: ${err.message}`, 'ai');
		} finally {
			this.inputEl.disabled = false;
			this.sendBtn.disabled = false;
			this.inputEl.focus();
		}
	}

	/* =======================================
	   Q&A TAB
	   ======================================= */
	buildQATab() {
		// Input Area
		const inputContainer = this.qaTabContent.createEl('div', { cls: 'lab-qa-input-container' });
		this.qaInputEl = inputContainer.createEl('textarea', { cls: 'lab-chat-input' });
		this.qaInputEl.placeholder = '遇到学术问题？向导师和全组提问...';
		this.qaSubmitBtn = inputContainer.createEl('button', { text: '发布问题', cls: 'lab-chat-send-btn' });
		this.qaSubmitBtn.onclick = () => this.submitQA();

		this.qaTabContent.createEl('hr');
		this.qaTabContent.createEl('h3', { text: '社区问答流' });
		
		this.qaListContainer = this.qaTabContent.createEl('div', { cls: 'lab-qa-list' });
	}

	async refreshQAList() {
		this.qaListContainer.empty();
		this.qaListContainer.createEl('div', { text: '加载中...', cls: 'lab-loading-text' });

		try {
			const res = await fetch(`${this.plugin.settings.serverUrl}/api/ai/server/qa`);
			if (!res.ok) throw new Error();
			const data = await res.json();
			const qaList = data.qa_list || [];
			
			this.qaListContainer.empty();
			if (qaList.length === 0) {
				this.qaListContainer.createEl('div', { text: '暂无社区提问。', cls: 'lab-empty-text' });
				return;
			}

			for (const qa of qaList) {
				const card = this.qaListContainer.createEl('div', { cls: 'lab-qa-card', attr: { style: 'position: relative;' } });
				
				const header = card.createEl('div', { attr: { style: 'display: flex; justify-content: space-between; align-items: flex-start;' } });
				header.createEl('div', { text: `❓ [${qa.student_name}] ${qa.question}`, cls: 'lab-qa-q', attr: { style: 'flex-grow: 1;' } });
				
				if (qa.student_name === this.plugin.settings.username) {
					const delQBtn = header.createEl('button', { text: '🗑️ 删除', cls: 'lab-chat-send-btn', attr: { style: 'background-color: var(--text-error); margin-left: 10px; padding: 2px 5px; height: 24px; font-size: 0.8em;' } });
					delQBtn.onclick = async () => {
						try {
							const res = await fetch(`${this.plugin.settings.serverUrl}/api/ai/server/qa/delete`, {
								method: 'DELETE',
								headers: { 'Content-Type': 'application/json' },
								body: JSON.stringify({ qa_id: qa.id, username: this.plugin.settings.username })
							});
							if (res.ok) {
								new Notice('问题已删除');
								this.refreshQAList();
							}
						} catch (e) {
							new Notice('删除失败');
						}
					};
				}
				
				const replies = qa.replies || [];
				if (replies.length > 0) {
					for (const rep of replies) {
						const repRow = card.createEl('div', { attr: { style: 'display: flex; justify-content: space-between; align-items: flex-start; margin-top: 5px;' } });
						const repEl = repRow.createEl('div', { cls: 'lab-qa-a', attr: { style: 'flex-grow: 1; margin-top: 0;' } });
						MarkdownRenderer.renderMarkdown(`**${rep.author}:** ${rep.content}`, repEl, '', this.plugin);
						
						if (rep.author === this.plugin.settings.username) {
							const delRBtn = repRow.createEl('button', { text: '撤回', cls: 'lab-chat-send-btn', attr: { style: 'background-color: var(--text-muted); margin-left: 10px; padding: 2px 5px; height: 24px; font-size: 0.8em;' } });
							delRBtn.onclick = async () => {
								try {
									const res = await fetch(`${this.plugin.settings.serverUrl}/api/ai/server/qa/reply/delete`, {
										method: 'DELETE',
										headers: { 'Content-Type': 'application/json' },
										body: JSON.stringify({ qa_id: qa.id, reply_id: rep.id, username: this.plugin.settings.username })
									});
									if (res.ok) {
										new Notice('回复已撤回');
										this.refreshQAList();
									}
								} catch (e) {
									new Notice('撤回失败');
								}
							};
						}
					}
				} else {
					card.createEl('div', { text: '等待导师、师兄或课题组其他成员解答...', cls: 'lab-qa-pending' });
				}
				card.createEl('div', { text: qa.created_at, cls: 'lab-qa-time' });

				// Add reply container
				const replyDiv = card.createEl('div', { cls: 'lab-qa-reply-box', attr: { style: 'margin-top: 10px; display: flex; gap: 5px;' } });
				const replyInput = replyDiv.createEl('input', { type: 'text', placeholder: '写下你的解答...', cls: 'lab-chat-input', attr: { style: 'flex-grow: 1; height: 30px;' } });
				const replyBtn = replyDiv.createEl('button', { text: '回复', cls: 'lab-chat-send-btn', attr: { style: 'height: 30px; padding: 0 10px;' } });
				replyBtn.onclick = async () => {
					const txt = replyInput.value.trim();
					if (!txt) return;
					replyBtn.disabled = true;
					try {
						const res = await fetch(`${this.plugin.settings.serverUrl}/api/ai/server/qa/reply`, {
							method: 'POST',
							headers: { 'Content-Type': 'application/json' },
							body: JSON.stringify({
								qa_id: qa.id,
								author_name: this.plugin.settings.username,
								reply_text: txt
							})
						});
						if (res.ok) {
							new Notice('回复成功！');
							this.refreshQAList();
						}
					} catch (e) {
						new Notice('回复失败，请检查网络。');
					} finally {
						replyBtn.disabled = false;
					}
				};
			}
		} catch (e) {
			this.qaListContainer.empty();
			this.qaListContainer.createEl('div', { text: '拉取社区数据失败。', cls: 'lab-error-text' });
		}
	}

	async submitQA() {
		const text = this.qaInputEl.value.trim();
		if (!text) return;

		this.qaInputEl.disabled = true;
		this.qaSubmitBtn.disabled = true;

		try {
			const res = await fetch(`${this.plugin.settings.serverUrl}/api/ai/server/qa/submit`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					student_name: this.plugin.settings.username,
					question: text
				})
			});

			if (res.ok) {
				new Notice('问题已发布至社区！');
				this.qaInputEl.value = '';
				this.refreshQAList();
			}
		} catch (e) {
			new Notice('发布失败，请检查网络。');
		} finally {
			this.qaInputEl.disabled = false;
			this.qaSubmitBtn.disabled = false;
		}
	}

	/* =======================================
	   HELPERS
	   ======================================= */
	addMessage(text: string, role: 'user' | 'ai') {
		const msgEl = this.messageContainer.createEl('div', { cls: `lab-chat-message ${role}` });
		msgEl.innerText = text;
		this.scrollToBottom(this.messageContainer);
	}

	async addMarkdownMessage(markdownText: string, role: 'ai', container: HTMLElement) {
		const msgEl = container.createEl('div', { cls: `lab-chat-message ${role}` });
		await MarkdownRenderer.renderMarkdown(markdownText, msgEl, '', this.plugin);
		this.scrollToBottom(container);
	}

	addLoadingIndicator(container: HTMLElement): string {
		const id = 'loading-' + Date.now();
		const msgEl = container.createEl('div', { cls: 'lab-chat-message ai', attr: { id } });
		const dots = msgEl.createEl('div', { cls: 'lab-typing-indicator' });
		dots.createEl('div', { cls: 'lab-typing-dot' });
		dots.createEl('div', { cls: 'lab-typing-dot' });
		dots.createEl('div', { cls: 'lab-typing-dot' });
		this.scrollToBottom(container);
		return id;
	}

	removeLoadingIndicator(container: HTMLElement, id: string) {
		const el = container.querySelector(`#${id}`);
		if (el) el.remove();
	}

	scrollToBottom(container: HTMLElement) {
		setTimeout(() => { container.scrollTop = container.scrollHeight; }, 50);
	}
}
