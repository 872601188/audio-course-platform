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
    async uploadAudio(files, courseId, titles = []) {
        const formData = new FormData();
        formData.append('course_id', courseId);
        files.forEach((file, i) => {
            formData.append('files', file);
            if (titles[i]) {
                formData.append(`title_${i}`, titles[i]);
            }
        });

        return fetch(`${API_BASE}/api/upload/audio`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
            body: formData
        }).then(r => r.json());
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
