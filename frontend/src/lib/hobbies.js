// Categorized hobby catalog for the profile Hobbies multi-select.
// Grouped by theme; users can pick up to HOBBY_MAX hobbies across any groups.
export const HOBBY_MAX = 10;

export const HOBBY_GROUPS = [
  {
    label: "🎨 Creative",
    options: ["Photography", "Drawing", "Painting", "Writing", "Poetry", "Pottery", "Ceramics", "Crafts", "Knitting", "Sewing", "Jewelry making", "DIY projects", "Graphic design", "Fashion", "Interior design", "Music production"],
  },
  {
    label: "🎵 Music",
    options: ["Singing", "Guitar", "Piano", "Drums", "Violin", "DJing", "Concerts", "Music festivals", "Karaoke", "Songwriting", "Vinyl collecting", "Discovering new music"],
  },
  {
    label: "🏃 Sports & Fitness",
    options: ["Running", "Gym", "Yoga", "Pilates", "Cycling", "Hiking", "Swimming", "Tennis", "Basketball", "Soccer", "Volleyball", "Golf", "Skiing", "Snowboarding", "Skating", "Dancing", "Martial arts", "Rock climbing"],
  },
  {
    label: "🌲 Outdoors & Adventure",
    options: ["Camping", "Fishing", "Kayaking", "Canoeing", "Paddleboarding", "Road trips", "Travel", "Exploring new places", "Stargazing", "Nature photography", "Gardening", "Beach days", "Picnics"],
  },
  {
    label: "🍳 Food & Lifestyle",
    options: ["Cooking", "Baking", "BBQ", "Trying restaurants", "Coffee", "Tea", "Wine tasting", "Food festivals", "Farmers' markets", "Healthy cooking", "Trying new cuisines"],
  },
  {
    label: "🎮 Entertainment",
    options: ["Movies", "TV shows", "Anime", "Gaming", "Board games", "Card games", "Puzzles", "Escape rooms", "Trivia", "Comics", "Reading", "Podcasts", "Stand-up comedy"],
  },
  {
    label: "📚 Learning & Intellectual",
    options: ["History", "Psychology", "Philosophy", "Science", "Languages", "Astronomy", "Coding", "Investing", "Entrepreneurship", "Online courses", "Museums", "Documentaries"],
  },
  {
    label: "🐾 Animals",
    options: ["Dogs", "Cats", "Horse riding", "Animal rescue", "Pet care", "Wildlife", "Bird watching", "Aquariums"],
  },
  {
    label: "💃 Social & Nightlife",
    options: ["Clubs", "Bars", "Live music", "Parties", "Festivals", "Social events", "Networking", "Meeting new people"],
  },
  {
    label: "✈️ Travel",
    options: ["Backpacking", "Luxury travel", "Weekend trips", "International travel", "Cruises", "City breaks", "Cultural tourism", "Adventure travel", "Travel photography"],
  },
  {
    label: "🧘 Relaxation & Wellness",
    options: ["Meditation", "Spa", "Skincare", "Journaling", "Walking", "Breathwork", "Self-development", "Mindfulness"],
  },
  {
    label: "🏠 Home & Collecting",
    options: ["Home decorating", "DIY", "Collecting books", "Collecting vinyl", "Collecting art", "Plants", "Antiques", "Thrifting"],
  },
];

// Groups formatted for the MultiSelect component ({label, options:[{value,label}]}).
export const HOBBY_SELECT_GROUPS = HOBBY_GROUPS.map((g) => ({
  label: g.label,
  options: g.options.map((h) => ({ value: h, label: h })),
}));
