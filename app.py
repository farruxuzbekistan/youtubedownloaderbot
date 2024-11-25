# Import required libraries
import logging
from aiogram import Bot, Dispatcher, executor, types  # Telegram bot framework
from yt_dlp import YoutubeDL  # YouTube downloader library
import os  # For file operations
import asyncio  # For asynchronous operations
import subprocess  # For running external commands (ffmpeg)

# Set up logging to track errors and info
logging.basicConfig(level=logging.INFO)

# Bot configuration settings
API_TOKEN = ""  # Your bot's API token
CHANNEL_USERNAME = "@farruhdeveloper"  # Channel username that users must join
CHANNEL_ID = -1001958514515  # Numeric ID of the channel
BOT_NAME = ""  # Your bot's username

# Create bot instance and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Configure YouTube download options
YTDL_OPTIONS = {
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",  # Get best quality video+audio
    "outtmpl": "%(title)s.%(ext)s",  # Output template for downloaded files
    "quiet": True,  # Suppress output
    "no_warnings": True,  # Don't show warnings
    "merge_output_format": "mp4",  # Final output format
}

# Store temporary data for callback queries
callback_data_store = {}


# Function to check if user is a channel member
async def is_user_member(user_id):
    """
    Check if a user is a member of the required channel
    Args:
        user_id: Telegram user ID
    Returns:
        bool: True if user is member, False otherwise
    """
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.warning(f"Error checking membership for user {user_id}: {e}")
        return False


# Function to convert video audio to MP3 format
def convert_to_mp3(input_path, output_path):
    """
    Convert downloaded audio to MP3 format using ffmpeg
    Args:
        input_path: Path to input audio file
        output_path: Path where MP3 should be saved
    """
    try:
        subprocess.run(
            ["ffmpeg", "-i", input_path, "-q:a", "0", "-map", "a", output_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        raise RuntimeError(f"Failed to convert audio to MP3: {e}")


# Function to get available video formats
def get_available_formats(url):
    """
    Extract available download formats for a YouTube video
    Args:
        url: YouTube video URL
    Returns:
        list: Available formats including video resolutions and audio
    """
    ydl_opts = {
        "quiet": True,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    }
    formats = []

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        # Add MP3 audio option
        formats.append({"type": "audio", "format_id": "bestaudio/best", "ext": "mp3"})

        # Add different video quality options
        resolutions = [1080, 720, 480, 360, 144]  # Available video qualities
        for resolution in resolutions:
            formats.append(
                {
                    "type": "video",
                    "height": resolution,
                    "format_id": f"bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]",
                    "ext": "mp4",
                }
            )

    return formats


# Handle /start command
@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    """
    Handle the /start command and check channel membership
    Args:
        message: Telegram message object
    """
    if not await is_user_member(message.from_user.id):
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(
                "Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
            ),
            types.InlineKeyboardButton(
                "Check Membership", callback_data="check_membership"
            ),
        )
        await message.reply(
            "⚠️ To use this bot, you need to join our Telegram channel first!",
            reply_markup=keyboard,
        )
        return
    await message.reply(
        "✅ Welcome! Send me a YouTube link to download videos or audio."
    )


# Handle membership check callback
@dp.callback_query_handler(lambda call: call.data == "check_membership")
async def check_membership(callback_query: types.CallbackQuery):
    """
    Handle membership verification callback
    Args:
        callback_query: Callback query from inline keyboard
    """
    user_id = callback_query.from_user.id
    try:
        is_member = await is_user_member(user_id)
        if is_member:
            new_text = "✅ Thank you for joining the channel! You can now use the bot. Send me a YouTube link to get started."
        else:
            new_text = "⚠️ You are not a member of our channel. Please join here:"

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(
                "Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
            ),
            types.InlineKeyboardButton(
                "Check Membership", callback_data="check_membership"
            ),
        )
        await callback_query.message.edit_text(new_text, reply_markup=keyboard)
    except Exception as e:
        logging.error(f"Error in check_membership: {e}")


# Handle YouTube links
@dp.message_handler(content_types=["text"])
async def handle_youtube_link(message: types.Message):
    """
    Process YouTube links sent by users
    Args:
        message: Telegram message containing YouTube URL
    """
    # Check channel membership
    if not await is_user_member(message.from_user.id):
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(
                "Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
            ),
            types.InlineKeyboardButton(
                "Check Membership", callback_data="check_membership"
            ),
        )
        await message.reply(
            "⚠️ To use this bot, you need to join our Telegram channel first!",
            reply_markup=keyboard,
        )
        return

    # Process YouTube URL
    url = message.text.strip()
    if "youtube.com" in url or "youtu.be" in url:
        status_msg = await message.reply(
            "🎥 Processing your YouTube link... Please wait."
        )
        formats = get_available_formats(url)
        if formats:
            # Create format selection keyboard
            keyboard = types.InlineKeyboardMarkup()
            for index, fmt in enumerate(formats):
                callback_data_store[str(index)] = {
                    "format_id": fmt["format_id"],
                    "url": url,
                    "type": fmt["type"],
                }
                button_label = (
                    f"{fmt['height']}p" if fmt["type"] == "video" else "Audio (MP3)"
                )
                keyboard.add(
                    types.InlineKeyboardButton(
                        button_label, callback_data=f"format_{index}"
                    )
                )
            await status_msg.edit_text("Choose your format:", reply_markup=keyboard)
        else:
            await status_msg.edit_text("❌ No suitable formats found.")
    else:
        await message.reply("❌ Please send a valid YouTube link.")


# Handle format selection
@dp.callback_query_handler(lambda call: call.data.startswith("format_"))
async def process_format_selection(callback_query: types.CallbackQuery):
    """
    Process user's format selection and download video/audio
    Args:
        callback_query: Callback query containing format selection
    """
    try:
        # Answer callback to prevent timeout
        await callback_query.answer()

        # Get selected format data
        format_index = int(callback_query.data.split("_")[1])
        format_data = callback_data_store.get(str(format_index))

        if not format_data:
            await callback_query.message.edit_text(
                "❌ Invalid format selection. Please try again."
            )
            return

        await callback_query.message.edit_text("⏳ Downloading... Please wait.")

        try:
            # Download with selected format
            ydl_opts = {**YTDL_OPTIONS, "format": format_data["format_id"]}
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(format_data["url"], download=True)
                file_path = ydl.prepare_filename(info)
                content_title = info.get("title", "Downloaded Content")

            # Handle audio conversion if needed
            if format_data["type"] == "audio":
                mp3_path = file_path.replace(file_path.split(".")[-1], "mp3")
                convert_to_mp3(file_path, mp3_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
                file_path = mp3_path

                # Send audio file
                with open(file_path, "rb") as audio_file:
                    await bot.send_audio(
                        chat_id=callback_query.message.chat.id,
                        audio=audio_file,
                        caption=f"🎵 {content_title}",
                        title=content_title,
                    )
            else:
                # Send video file
                with open(file_path, "rb") as video_file:
                    await bot.send_video(
                        chat_id=callback_query.message.chat.id,
                        video=video_file,
                        caption=f"🎥 {content_title}",
                    )

            # Clean up downloaded file
            if os.path.exists(file_path):
                os.remove(file_path)

            await callback_query.message.edit_text("✅ Download completed!")

        except Exception as e:
            logging.error(f"Error downloading content: {e}")
            await callback_query.message.edit_text(
                "❌ Failed to download. Please try again."
            )

    except Exception as e:
        logging.error(f"Error in format selection: {e}")
        await callback_query.message.edit_text(
            "❌ An error occurred. Please try again."
        )


# Start the bot
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
