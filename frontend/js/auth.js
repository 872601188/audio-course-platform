/**
 * 认证管理模块 - 处理登录状态、用户信息
 */

// 初始化：检查登录状态
function initAuth() {
    const token = localStorage.getItem('access_token');
    const user = JSON.parse(localStorage.getItem('user') || 'null');

    // 更新导航栏用户信息显示
    updateNavUser(user);

    return { token, user };
}

function updateNavUser(user) {
    const navUser = document.getElementById('nav-user');
    if (!navUser) return;

    if (user) {
        const isAdmin = user.role === 'admin';
        navUser.innerHTML = `
            <div class="relative group">
                <button class="flex items-center gap-1 text-sm text-gray-700 hover:text-blue-600 py-2">
                    <span class="font-medium">${user.username}</span>
                    ${isAdmin ? '<span class="text-xs text-gray-400">(管理员)</span>' : ''}
                    <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                    </svg>
                </button>
                <div class="absolute right-0 mt-0 w-40 bg-white rounded-lg shadow-lg border border-gray-100 hidden group-hover:block z-50">
                    <a href="/settings.html" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 hover:text-blue-600 rounded-t-lg">
                        ⚙️ 个人设置
                    </a>
                    <a href="/admin.html" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 hover:text-blue-600 ${isAdmin ? '' : 'hidden'}">
                        🔧 管理后台
                    </a>
                    <button onclick="AuthAPI.logout()" class="w-full text-left px-4 py-2 text-sm text-red-500 hover:bg-red-50 hover:text-red-700 rounded-b-lg">
                        🚪 退出登录
                    </button>
                </div>
            </div>
        `;
    } else {
        navUser.innerHTML = `
            <a href="/login.html" class="text-sm text-blue-600 hover:text-blue-800">登录</a>
        `;
    }
}

// 检查是否已登录
function requireAuth() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login.html?redirect=' + encodeURIComponent(window.location.pathname);
        return false;
    }
    return true;
}

// 检查管理员权限
function requireAdmin() {
    if (!requireAuth()) return false;
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    if (!user || user.role !== 'admin') {
        alert('权限不足，需要管理员权限');
        window.location.href = '/';
        return false;
    }
    return true;
}

// 格式化时长显示 (秒 -> MM:SS 或 HH:MM:SS)
function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '00:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// 格式化日期
function formatDate(dateStr) {
    if (!dateStr) return '未知';
    const d = new Date(dateStr);
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}