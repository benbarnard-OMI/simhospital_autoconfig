import yaml
Loader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
with open('data.yml', 'r') as f:
    data = yaml.load(f, Loader=Loader)
print(type(data))
