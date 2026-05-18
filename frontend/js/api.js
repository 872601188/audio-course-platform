/**
 * API 封装模块 - 统一处理后端接口调用
 * 包含认证、课程、上传、播放器和分析接口
 */

const API_BASE = window.location.origin;  // 自动适配当前域名

// 默认请求头
function getHeaders() {
    const token = localStorage.getItem('access_token');
    const headers = {
        'Content-Type': 'application/json'
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

/**
 * 通用 fetch 封装
 */
async function apiFetch(url, options = {}) {
    const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`;
    const response = await fetch(fullUrl, {
        ...options,
        headers: {
            ...getHeaders(),
            ...(options.headers || {})
        }
    });

    // 处理认证失效
    if (response.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        window.location.href = '/login.html';
        throw new Error('认证已过期，请重新登录');
    }

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || `请求失败 (${response.status})`);
    }
    return data;
}

// ========== 认证 API ==========

const AuthAPI = {
    async register(username, email, password, role = 'student') {
        return apiFetch('/api/register', {
            method: 'POST',
            body: JSON.stringify({ username, email, password, role })
        });
    },

    async login(username, password) {
        return apiFetch('/api/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
    },

    async getMe() {
        return apiFetch('/api/me');
    },

    logout() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        window.location.href = '/login.html';
    }
};

// ========== 课程 API ==========

const CourseAPI = {
    async getList(params = {}) {
        const query = new URLSearchParams(params);
        return apiFetch(`/api/courses?${query}`);
    },

    async getDetail(courseId) {
        return apiFetch(`/api/courses/${courseId}`);
    },

    async create(data) {
        return apiFetch('/api/courses', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async update(courseId, data) {
        return apiFetch(`/api/courses/${courseId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    async delete(courseId) {
        return apiFetch(`/api/courses/${courseId}`, {
            method: 'DELETE'
        });
    },

    async reorder(courseId, orders) {
        return apiFetch(`/api/courses/${courseId}/reorder`, {
            method: 'POST',
            body: JSON.stringify({ orders })
        });
    }
};

// ========== 上传 API ==========

const UploadAPI = {
    /**
     * 上传音频（支持进度回调）
     * @param {File[]} files 文件列表
     * @param {number} courseId 课程ID
     * @param {string[]} titles 标题列表
     * @param {function} onProgress 进度回调 (event) => void
     *   event: { loaded, total, percent, fileIndex, fileCount, fileName, speed }
     */
    uploadAudio(files, courseId, titles = [], onProgress = null) {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            formData.append('course_id', courseId);
            files.forEach((file, i) => {
                formData.append('files', file);
                if (titles[i]) {
                    formData.append(`title_${i}`, titles[i]);
                }
            });

            const xhr = new XMLHttpRequest();
            const token = localStorage.getItem('access_token');

            xhr.open('POST', `${API_BASE}/api/upload/audio`);
            if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

            // 进度监控
            if (onProgress && xhr.upload) {
                let lastLoaded = 0;
                let lastTime = Date.now();
                xhr.upload.onprogress = (e) => {
                    if (!e.lengthComputable) return;
                    const now = Date.now();
                    const dt = (now - lastTime) / 1000;
                    const speed = dt > 0 ? (e.loaded - lastLoaded) / dt : 0;
                    lastLoaded = e.loaded;
                    lastTime = now;

                    // 计算每个文件的大致进度（基于文件大小比例）
                    const totalSize = files.reduce((s, f) => s + f.size, 0);
                    let cumulative = 0;
                    let currentIndex = 0;
                    for (let i = 0; i < files.length; i++) {
                        if (cumulative + files[i].size >= e.loaded) {
                            currentIndex = i;
                            break;
                        }
                        cumulative += files[i].size;
                    }

                    onProgress({
                        loaded: e.loaded,
                        total: e.total,
                        percent: Math.round((e.loaded / e.total) * 100),
                        fileIndex: currentIndex,
                        fileCount: files.length,
                        fileName: files[currentIndex]?.name || '',
                        speed: speed
                    });
                };
            }

            xhr.onload = () => {
                try {
                    const data = JSON.parse(xhr.responseText);
                    if (xhr.status >= 200 && xhr.status < 300) {
                        resolve(data);
                    } else if (xhr.status === 401) {
                        localStorage.removeItem('access_token');
                        localStorage.removeItem('user');
                        window.location.href = '/login.html';
                        reject(new Error('认证已过期，请重新登录'));
                    } else {
                        reject(new Error(data.error || `上传失败 (${xhr.status})`));
                    }
                } catch {
                    reject(new Error('解析响应失败'));
                }
            };

            xhr.onerror = () => reject(new Error('网络错误，上传失败'));
            xhr.ontimeout = () => reject(new Error('上传超时'));
            xhr.onabort = () => reject(new Error('上传已取消'));

            xhr.send(formData);
        });
    },

    async uploadCover(file) {
        const formData = new FormData();
        formData.append('file', file);

        return fetch(`${API_BASE}/api/upload/cover`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
            body: formData
        }).then(r => r.json());
    }
};

// ========== 播放器 API ==========

const PlayerAPI = {
    async getProgress(audioId) {
        return apiFetch(`/api/progress/${audioId}`);
    },

    async saveProgress(audioId, currentTime, completed = false) {
        return apiFetch(`/api/progress/${audioId}`, {
            method: 'POST',
            body: JSON.stringify({ current_time: currentTime, completed })
        });
    },

    async logAction(audioId, action, position, durationListened = 0) {
        return apiFetch('/api/progress', {
            method: 'POST',
            body: JSON.stringify({
                audio_id: audioId,
                action,
                position,
                duration_listened: durationListened
            })
        });
    },

    async getAllProgress() {
        return apiFetch('/api/progress/all');
    }
};

// ========== 收藏 API ==========

const FavoriteAPI = {
    async toggle(audioId) {
        return apiFetch(`/api/favorites/${audioId}`, { method: 'POST' });
    },

    async check(audioId) {
        return apiFetch(`/api/favorites/${audioId}`);
    },

    async list() {
        return apiFetch('/api/favorites');
    },

    async clear() {
        return apiFetch('/api/favorites', { method: 'DELETE' });
    }
};

// ========== 分析 API ==========

const AnalyzeAPI = {
    async analyze(days = 30) {
        return apiFetch('/api/analyze-plan', {
            method: 'POST',
            body: JSON.stringify({ days })
        });
    },

    async getStats() {
        return apiFetch('/api/learning-stats');
    }
};
