import asyncio
import ctypes
import datetime
import inspect
import logging
import threading
import time
from enum import Enum
from typing import Dict

import discord
from mbot.core.plugins import PluginMeta
from mbot.core.plugins import plugin
from mbot.openapi import mbot_api

server = mbot_api
_LOGGER = logging.getLogger(__name__)

MY_GUILD = []
TOKEN = None
PROXY = None
bot = None
DiscordThread = None
CHANNEL_ID = None
LOG_IGNORE_WORDS = None

# 网上找的，用于强制关闭线程
class StoppableThread(threading.Thread):
    def _async_raise(self, tid, exctype):
        """raises the exception, performs cleanup if needed"""
        tid = ctypes.c_long(tid)
        if not inspect.isclass(exctype):
            exctype = type(exctype)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
        if res == 0:
            _LOGGER.warning("DiscordBot:线程不存在，无法杀死")
            return False
        elif res != 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    def stop_thread(self, thread):
        if thread is not None:
            self._async_raise(thread.ident, SystemExit)
        else:
            return None


@plugin.after_setup
def _(plugin: PluginMeta, config: Dict):
    global PROXY, MY_GUILD, TOKEN, bot, DiscordThread, CHANNEL_ID, LOG_IGNORE_WORDS
    PROXY = config.get("proxy")
    CHANNEL_ID = config.get("channel_id")
    LOG_IGNORE_WORDS = config.get("log_ignore_words") if config.get("log_ignore_words") else None
    _MY_GUILD_raw = config.get("guild_id")
    TOKEN = config.get("token")
    if not TOKEN:
        StoppableThread().stop_thread(DiscordThread)
        _LOGGER.error("DiscordBot:你没有配置token，bot已停止！请配置token")
        return
    if _MY_GUILD_raw:
        MY_GUILD = _MY_GUILD_raw.split(",")
        for i in range(len(MY_GUILD)):
            MY_GUILD[i] = discord.Object(id=MY_GUILD[i])
    else:
        StoppableThread().stop_thread(DiscordThread)
        _LOGGER.error("DiscordBot:你没有配置服务器id，bot已停止！请配置服务器id")
        return
    _LOGGER.info(
        f"DiscordBot:插件加载成功, proxy:{PROXY}, token:{TOKEN[:15] + '**********'}, 服务器id:{_MY_GUILD_raw}, 频道id:{CHANNEL_ID}, 跳过词:{LOG_IGNORE_WORDS}\n如果下方有”已登录“字样的日志，说明bot已经启动成功")
    intents = discord.Intents.default()
    bot = StartBot(intents=intents, proxy=PROXY if PROXY else None)
    set_commands()
    DiscordThread = threading.Thread(target=bot.run, args=(TOKEN,), name="DiscordBot")
    DiscordThread.start()


@plugin.config_changed
def _(config: Dict):
    global DiscordThread, TOKEN, bot, PROXY, MY_GUILD, CHANNEL_ID, LOG_IGNORE_WORDS
    _LOGGER.info("DiscordBot:收到配置变更信号，正在应用新配置，无需重启")
    PROXY = config.get("proxy")
    LOG_IGNORE_WORDS = config.get("log_ignore_words") if config.get("log_ignore_words") else None
    CHANNEL_ID = config.get("channel_id")
    _MY_GUILD_raw = config.get("guild_id")
    TOKEN = config.get("token")
    if not TOKEN:
        StoppableThread().stop_thread(DiscordThread)
        _LOGGER.error("DiscordBot:你没有配置token，bot已停止！请配置token")
        return
    if _MY_GUILD_raw:
        MY_GUILD = _MY_GUILD_raw.split(",")
        for i in range(len(MY_GUILD)):
            MY_GUILD[i] = discord.Object(id=MY_GUILD[i])
    else:
        StoppableThread().stop_thread(DiscordThread)
        _LOGGER.error("DiscordBot:你没有配置服务器id，bot已停止！请配置服务器id")
        return
    _LOGGER.info(
        f"DiscordBot:配置变更成功, proxy:{PROXY}, token:{TOKEN[:15] + '**********'}, 服务器id:{_MY_GUILD_raw}, 频道id:{CHANNEL_ID}, 跳过词:{LOG_IGNORE_WORDS}")
    StoppableThread().stop_thread(DiscordThread)
    intents = discord.Intents.default()
    bot = StartBot(intents=intents, proxy=PROXY if PROXY else None)
    set_commands()
    DiscordThread = threading.Thread(target=bot.run, args=(TOKEN,), name="DiscordBot")
    DiscordThread.start()

class MessageTemplete:
    """ 消息模板 """

    def build_embed(self, douban_id, is_from_hot_list=False):
        """ 使用豆瓣id构建Embed卡片 返回构建好的单个Embed """
        t1 = time.time()
        _LOGGER.info(f"开始获取 豆瓣id：{douban_id} 的详细影片信息")
        douban_get = server.douban.get(douban_id)
        meta = server.meta.get_media_by_douban(media_type=douban_get.media_type, tmdb_id=douban_id)
        try:
            genres = ' / '.join(i for i in meta.genres)
            country = ' / '.join(i for i in meta.country)
            premiere_date = meta.premiere_date
            poster_url = meta.poster_url
            background_url = meta.background_url
            title = meta.title
            intro = meta.intro
        except AttributeError:
            _LOGGER.info("获取自建元数据失败，使用豆瓣信息")
            genres = ' / '.join(i for i in douban_get.genres) if douban_get.genres else "暂无"
            country = ' / '.join(i for i in douban_get.country) if douban_get.country else "暂无"
            premiere_date = douban_get.premiere_date
            poster_url = douban_get.cover_image
            background_url = None
            title = douban_get.cn_name
            intro = douban_get.intro
        if douban_get.media_type == "TV":
            type = "📺"
        else:
            type = "🎬"
        url = douban_get.url
        if is_from_hot_list:
            description = intro
        else:
            description = intro[:200] + "······" if len(intro) >= 200 else intro
        embed = discord.Embed(title=type + " " + title, description=description, url=url)
        if premiere_date is None:
            premiere_date = "未播出"
        embed.set_footer(text=f"首播时间：{premiere_date}")
        embed.add_field(name="区域", value=country)
        embed.add_field(name="类型", value=genres)
        embed.set_thumbnail(url=poster_url)
        embed.set_author(name="MovieRobot")
        embed.set_image(url=background_url)
        t2 = time.time()
        _LOGGER.info("构建embed消耗时间：" + str((t2 - t1) * 1000) + "ms")
        return embed

    def build_menu(self, keyword):
        """ 构造由 豆瓣id+名称 组成的菜单，供用户选择后调用embed发送影片详情 """
        _LOGGER.info(f"开始获取 关键词：{keyword} 的搜索结果")
        menu = discord.ui.Select()
        search_res = server.douban.search(keyword)
        if not search_res:
            return None
        for i in range(len(search_res)):
            if search_res[i].status is None:
                status = '3'
            else:
                status = str(search_res[i].status.value)
            if status == '0':
                emoji = "⏳"
            elif status == '1':
                emoji = "✔"
            elif status == '2':
                emoji = "🔁"
            else:
                emoji = "📥"
            if str(search_res[i].rating) == "nan":
                rating = "0.0"
            else:
                rating = str(search_res[i].rating)
            menu.add_option(label=" | ⭐" + rating + " | " + search_res[i].cn_name,
                            value=str(search_res[i].id) + " " + status, emoji=emoji)
        menu.callback = Callback().menu_callback
        return menu

    def build_button(self, douban_id, status):
        """ 构造一级菜单按钮：取消、订阅 """
        cancel_button = discord.ui.Button(label="关闭", custom_id="cancel", style=discord.ButtonStyle.danger, emoji="❌")
        if status == 0:
            status = '正在订阅️'
            status_disabled = True
            emoji = "⏳"
        elif status == 1:
            status = '订阅完成'
            status_disabled = True
            emoji = "✔"
        elif status == 2:
            status = '正在洗版'
            status_disabled = True
            emoji = "🔁"
        else:
            status = '即刻订阅'
            status_disabled = False
            emoji = "📥"
        sub_button = discord.ui.Button(label=status, custom_id=douban_id, style=discord.ButtonStyle.success,
                                       disabled=status_disabled, emoji=emoji)
        # cancel_button.callback = Callback().cancel_button_callback
        # sub_button.callback = Callback().subscribe_button_callback
        return cancel_button, sub_button

    def build_filter_button(self):
        """ 构建过滤器选择界面按钮 """
        filters = []
        view = discord.ui.View()
        cancel_button = discord.ui.Button(label="取消", custom_id="cancel", style=discord.ButtonStyle.danger, emoji="❌")
        cancel_button.callback = Callback().cancel_button_callback
        view.add_item(cancel_button)
        filters_get = server.subscribe.get_filters()
        auto_filter = discord.ui.Button(label="自动选择过滤器", custom_id="auto_filter",
                                        style=discord.ButtonStyle.primary, emoji="⚙️")
        auto_filter.callback = Callback().subscirbe
        view.add_item(auto_filter)
        for i in range(len(filters_get)):
            temp = discord.ui.Button(label=filters_get[i].filter_name, custom_id=filters_get[i].filter_name,
                                     style=discord.ButtonStyle.primary, emoji='⌛')
            temp.callback = Callback().subscirbe
            view.add_item(temp)
        return view


class Callback:
    """ 回调函数 """
    douban_id = None
    hot_list = None

    async def menu_callback(self, interaction: discord.Interaction):
        """ 一级菜单回调函数 """
        await interaction.response.defer(ephemeral=True, thinking=True)
        view = discord.ui.View()
        build_msg = MessageTemplete()
        douban_id, status = interaction.data.get("values")[0].split(" ")
        btn1, btn2 = build_msg.build_button(douban_id, int(status))
        btn1.callback = Callback().cancel_button_callback
        btn2.callback = Callback().subscribe_button_callback
        view.add_item(btn1)
        view.add_item(btn2)
        await interaction.followup.send('', embed=build_msg.build_embed(douban_id=douban_id), ephemeral=True, view=view)

    async def cancel_button_callback(self, interaction: discord.Interaction):
        """ 取消按钮回调函数 """
        _LOGGER.info("删除消息")
        await interaction.response.edit_message(content="这次取消了，下次一定哦！", view=None, embed=None)
        await asyncio.sleep(2.0)
        await interaction.delete_original_response()

    async def subscribe_button_callback(self, interaction: discord.Interaction):
        """ 订阅按钮回调函数 """
        build_msg = MessageTemplete()
        Callback.douban_id = interaction.data.get("custom_id")
        view = build_msg.build_filter_button()
        await interaction.response.edit_message(view=view)

    async def subscirbe(self, interaction: discord.Interaction):
        """ 订阅 """
        filter = interaction.data.get("custom_id") if interaction.data.get("custom_id") != "auto_filter" else None
        _LOGGER.info(f"开始订阅{Callback.douban_id}")
        server.subscribe.sub_by_douban(douban_id=Callback.douban_id, filter_name=filter)
        filter_msg = f"使用 {filter} 过滤器" if filter else "自动选择过滤器"
        await interaction.response.edit_message(content=f"✔ {filter_msg}订阅成功！", embed=None, view=None)
        await asyncio.sleep(2.0)
        await interaction.delete_original_response()

    async def hot_menu_callback(self, interaction: discord.Interaction):
        """ 可选热门榜单回调函数 """
        await interaction.response.defer()
        hot_list_name = interaction.data.get("values")[0]
        _LOGGER.info(f"获取{hot_list_name}热门列表")
        Callback.hot_list = server.douban.list_ranking(DoubanRankingType.get(hot_list_name))
        menu = discord.ui.Select()
        for i in range(len(Callback.hot_list)):
            menu.add_option(
                label=f"第{i + 1}名 | ⭐{str(Callback.hot_list[i].rating)} | {Callback.hot_list[i].cn_name}",
                value=str(Callback.hot_list[i].id), emoji="🏆")
        menu.add_option(label="一键全部订阅", value="all", emoji="⚙️")
        menu.placeholder = "🔎 请选择影片"
        menu.callback = Callback().hot_list_callback
        await interaction.edit_original_response(content="", view=discord.ui.View().add_item(menu))

    async def hot_list_callback(self, interaction: discord.Interaction):
        """ 单个热门榜单内容回调函数 """
        await interaction.response.defer()
        build_msg = MessageTemplete()
        douban_id = interaction.data.get("values")[0]
        if douban_id == "all":
            for i in range(len(Callback.hot_list)):
                server.subscribe.sub_by_douban(douban_id=Callback.hot_list[i].id)
            await interaction.edit_original_response(content="✔ 一键订阅所有影片成功！", embed=None, view=None)
            await asyncio.sleep(2.0)
            await interaction.delete_original_response()
        else:
            btn1, btn2 = build_msg.build_button(douban_id, 3)
            btn1.callback = Callback().cancel_button_callback
            btn2.callback = Callback().subscribe_button_callback
            view = discord.ui.View()
            view.add_item(btn1)
            view.add_item(btn2)
            await interaction.followup.send(content="",
                                            embed=build_msg.build_embed(douban_id=douban_id, is_from_hot_list=True),
                                            view=view)


class StartBot(discord.Client):
    """ 启动机器人 """
    def __init__(self, *, intents: discord.Intents, proxy):
        super().__init__(intents=intents, proxy=proxy)
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self):
        """ 设置启动钩子 同步应用命令 创建错误日志获取循环 """
        try:
            for i in range(len(MY_GUILD)):
                self.tree.copy_global_to(guild=MY_GUILD[i])
                await self.tree.sync(guild=MY_GUILD[i])
        except AttributeError as e:
            _LOGGER.info("没有设置服务器id，无法同步应用命令，跳过")
        except discord.errors.Forbidden as e:
            _LOGGER.warning(f"服务器id：{MY_GUILD[i]} 无权限，可能是获取的id不正确，请按照教程重新获取！")
        bot.loop.create_task(ReportLog().run_log_loop())

    async def on_ready(self):
        """ 启动时执行 """
        _LOGGER.info(f"已登录：{self.user}")
        await self.change_presence(status=discord.Status.online,
                                   activity=discord.Activity(type=discord.ActivityType.listening, name='/search'))


class GetLog:
    """ 通过mr sdk获取日志 """
    def __init__(self, session):
        self._ = session

    def getlog(self):
        res = self._.get('common.get_log_lines', params={'log_file': "robot.log"})
        return res


class ReportLog:
    """ 向指定频道报告日志错误 """

    def compare_time(self, time1, time2):
        """ 比较时间大小 """
        time1 = time.strptime(time1, "%Y/%m/%d %H:%M:%S")
        time2 = time.strptime(time2, "%Y/%m/%d %H:%M:%S")
        if time1 > time2:
            return True
        else:
            return False

    def get_new_err_log(self, last_error_time):
        """ 获取最新的错误日志 """
        if LOG_IGNORE_WORDS:
            ignore_words = LOG_IGNORE_WORDS.split(",")
        else:
            ignore_words = []
        log = GetLog(server.session).getlog()
        for i in reversed(range(len(log))):
            if "ERROR" in log[i]:
                try:
                    if "Traceback" in log[i + 1]:
                        for p in range(100):
                            try:
                                if "Error" in log[i + p]:
                                    temp = ""
                                    for key in range(p + 1):
                                        temp += log[i + key].strip() + "\n\n"
                                        for word in ignore_words:
                                            if word in temp:
                                                return None, last_error_time
                                    err_time = log[i].split(" - ")[0][1:]
                                    if self.compare_time(err_time, last_error_time):
                                        return temp, err_time
                            except IndexError:
                                pass
                except IndexError:
                    for word in ignore_words:
                        if word in log[i]:
                            return None, last_error_time
                    err_time = log[i].split(" - ")[0][1:]
                    if self.compare_time(err_time, last_error_time):
                        return log[i], err_time
        return None, last_error_time

    async def run_log_loop(self):
        """ 运行获取最新错误日志循环 """
        global last_err_time
        await bot.wait_until_ready()
        last_err_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        if not CHANNEL_ID:
            _LOGGER.info("没有设置频道id，无法发送错误日志，跳过")
            return None
        channel = bot.get_channel(int(CHANNEL_ID))
        if channel is None:
            _LOGGER.warning("频道id错误，无法发送错误日志，跳过")
            return None
        while not bot.is_closed():
            log, last_err_time = self.get_new_err_log(last_err_time)
            if log is not None:
                log = log if len(log) <= 1900 else log[:1900] + "\n\n......\n日志过长已截断"
                embed = discord.Embed(title="日志报错",
                                      description=f"发生时间：{last_err_time}\n```python\n" + log + "```",
                                      color=0xff0000)
                embed.set_author(name="MovieRobot")
                await channel.send("", embed=embed)
            await asyncio.sleep(5)


class DoubanRankingType(Enum):
    """ 豆瓣排行榜类型 """
    movie_real_time_hotest = '实时热门电影'
    movie_weekly_best = '一周口碑电影榜'
    ECPE465QY = '近期热门电影榜'
    EC7Q5H2QI = '近期高分电影榜'

    tv_chinese_best_weekly = '华语口碑剧集榜'
    tv_global_best_weekly = '全球口碑剧集榜'
    show_chinese_best_weekly = '国内口碑综艺榜'
    show_global_best_weekly = '国外口碑综艺榜'

    ECFA5DI7Q = '近期热门美剧'
    EC74443FY = '近期热门大陆剧'
    ECNA46YBA = '近期热门日剧'
    ECBE5CBEI = '近期热门韩剧'

    ECAYN54KI = '近期热门喜剧'
    ECBUOLQGY = '近期热门动作'
    ECSAOJFTA = '近期热门爱情'
    ECZYOJPLI = '近期热门科幻'
    EC3UOBDQY = '近期热门动画'
    ECPQOJP5Q = '近期热门悬疑'

    @classmethod
    def get(cls, value: str):
        return cls(value)


def set_commands():
    """设置应用命令"""

    @bot.tree.command()
    @discord.app_commands.describe(
        keyword="关键词",
    )
    async def search(interaction: discord.Interaction, keyword: str):
        """ 通过关键词搜索影片 """
        await interaction.response.defer()
        build_msg = MessageTemplete()
        view = discord.ui.View()
        menu = build_msg.build_menu(keyword)
        if menu is None:
            await interaction.followup.send(f"没有找到与”{keyword}“相关影片，请尝试更换关键词")
            await asyncio.sleep(10.0)
            await interaction.delete_original_response()
            return None
        menu.placeholder = "🔎 请选择影片"
        await interaction.followup.send("", view=view.add_item(menu))
        await asyncio.sleep(600.0)
        await interaction.delete_original_response()

    @bot.tree.command()
    async def hot(interaction: discord.Interaction):
        """ 获取豆瓣热门榜单影片 """
        build_msg = MessageTemplete()
        view = discord.ui.View()
        menu = discord.ui.Select()
        hot_list = [item.value for item in DoubanRankingType]
        for i in hot_list:
            menu.add_option(label="🔥 " + str(i), value=str(i))
        menu.callback = Callback().hot_menu_callback
        menu.placeholder = "🔥 请选择要查看的热门榜单"
        await interaction.response.send_message("", view=view.add_item(menu), delete_after=600.0)
